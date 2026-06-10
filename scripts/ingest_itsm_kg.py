"""
Ingest ITSM_data.csv into the Knowledge Graph.
This dataset has no free text — it's structured metadata for KG mining.
Extracts: CI entities, priority patterns, KB article links, incident relationships.
"""
import sys, os, uuid, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

import pandas as pd
from src.ekc.db.session import SessionLocal
from src.ekc.db.models import Entity, EntityRelationship, RelationshipType

ITSM_PATH = "data/raw/ITSM_data.csv"
BATCH_SIZE = 1000


def get_or_create_entity(db, canonical_name, entity_type, aliases=None):
    entity = db.query(Entity).filter(
        Entity.canonical_name == canonical_name
    ).first()
    if not entity:
        entity = Entity(
            entity_id=str(uuid.uuid4()),
            canonical_name=canonical_name,
            entity_type=entity_type,
            aliases=aliases or [canonical_name],
        )
        db.add(entity)
        db.flush()
    return entity


def get_or_create_relationship(db, source_id, target_id, rel_type, weight=1.0):
    existing = db.query(EntityRelationship).filter(
        EntityRelationship.source_entity_id == source_id,
        EntityRelationship.target_entity_id == target_id,
        EntityRelationship.relationship_type == rel_type,
    ).first()
    if not existing:
        db.add(EntityRelationship(
            rel_id=str(uuid.uuid4()),
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=rel_type,
            weight=weight,
        ))
        return True
    return False


def main():
    logger.info(f"Loading {ITSM_PATH}")
    df = pd.read_csv(ITSM_PATH, low_memory=False)
    logger.info(f"Loaded {len(df)} records")

    # Clean up
    df = df.fillna("")
    df['Priority'] = pd.to_numeric(df['Priority'], errors='coerce').fillna(4)

    db = SessionLocal()
    entities_created = 0
    relationships_created = 0

    try:
        # Pre-create priority entities
        priority_entities = {}
        for p, label in [(1, "P1-Critical"), (2, "P2-High"),
                         (3, "P3-Medium"), (4, "P4-Low")]:
            e = get_or_create_entity(db, f"priority:{label}", "Priority",
                                     [label, f"Priority {p}"])
            priority_entities[p] = e
            entities_created += 1

        # Pre-create category entities
        category_entities = {}
        for cat in df['Category'].unique():
            if cat:
                canonical = f"category:{cat.lower().replace(' ', '_')}"
                e = get_or_create_entity(db, canonical, "Category", [cat])
                category_entities[cat] = e
                entities_created += 1

        # Pre-create CI category entities
        ci_cat_entities = {}
        for ci_cat in df['CI_Cat'].unique():
            if ci_cat:
                canonical = f"ci_category:{ci_cat.lower().replace(' ', '_')}"
                e = get_or_create_entity(db, canonical, "Technology", [ci_cat])
                ci_cat_entities[ci_cat] = e
                entities_created += 1

        db.commit()
        logger.info(f"Created {entities_created} base entities")

        # Process records in batches
        batch_entities = 0
        batch_rels = 0

        for i, row in df.iterrows():
            # CI entity
            ci_name = str(row['CI_Name']).strip()
            if not ci_name or ci_name == 'nan':
                continue

            canonical_ci = f"ci:{ci_name.lower()}"
            ci_entity = get_or_create_entity(
                db, canonical_ci, "Technology",
                [ci_name, row['CI_Subcat']] if row['CI_Subcat'] else [ci_name]
            )
            batch_entities += 1

            # CI → Category relationship
            cat = str(row['Category']).strip()
            if cat and cat in category_entities:
                if get_or_create_relationship(
                    db, ci_entity.entity_id,
                    category_entities[cat].entity_id,
                    RelationshipType.belongs_to
                ):
                    batch_rels += 1

            # CI → CI_Category relationship
            ci_cat = str(row['CI_Cat']).strip()
            if ci_cat and ci_cat in ci_cat_entities:
                if get_or_create_relationship(
                    db, ci_entity.entity_id,
                    ci_cat_entities[ci_cat].entity_id,
                    RelationshipType.belongs_to
                ):
                    batch_rels += 1

            # CI → Priority relationship (weighted by frequency)
            priority = int(row['Priority']) if row['Priority'] else 4
            if priority in priority_entities:
                if get_or_create_relationship(
                    db, ci_entity.entity_id,
                    priority_entities[priority].entity_id,
                    RelationshipType.related_to,
                    weight=float(row.get('number_cnt', 1.0)),
                ):
                    batch_rels += 1

            # KB article entity and relationship
            kb = str(row['KB_number']).strip()
            if kb and kb != 'nan':
                kb_entity = get_or_create_entity(
                    db, f"kb:{kb.lower()}", "Ticket", [kb]
                )
                batch_entities += 1
                if get_or_create_relationship(
                    db, ci_entity.entity_id,
                    kb_entity.entity_id,
                    RelationshipType.resolves
                ):
                    batch_rels += 1

            # Related change
            related_change = str(row['Related_Change']).strip()
            if related_change and related_change != 'nan':
                change_entity = get_or_create_entity(
                    db, f"change:{related_change.lower()}", "Ticket",
                    [related_change]
                )
                batch_entities += 1
                if get_or_create_relationship(
                    db, ci_entity.entity_id,
                    change_entity.entity_id,
                    RelationshipType.related_to
                ):
                    batch_rels += 1

            # Commit in batches
            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                entities_created += batch_entities
                relationships_created += batch_rels
                logger.info(
                    f"  Processed {i+1}/{len(df)} records | "
                    f"entities: +{batch_entities} | rels: +{batch_rels}"
                )
                batch_entities = 0
                batch_rels = 0

        # Final commit
        db.commit()
        entities_created += batch_entities
        relationships_created += batch_rels

        # Summary
        total_entities = db.query(Entity).count()
        total_rels = db.query(EntityRelationship).count()

        logger.info("=" * 60)
        logger.info("ITSM KG INGESTION COMPLETE")
        logger.info(f"  Records processed: {len(df)}")
        logger.info(f"  New entities created: {entities_created}")
        logger.info(f"  New relationships created: {relationships_created}")
        logger.info(f"  Total entities in KG: {total_entities}")
        logger.info(f"  Total relationships in KG: {total_rels}")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()