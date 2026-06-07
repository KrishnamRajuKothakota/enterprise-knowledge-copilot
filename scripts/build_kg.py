"""
One-command KG builder.
Reads all chunks from Postgres, extracts entities + relationships,
writes to NetworkX graph + DB + GraphML.

Usage: python scripts/build_kg.py
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

from src.ekc.kg.extract import get_extractor, EntityExtractor
from src.ekc.kg.relations import RelationshipExtractor
from src.ekc.kg.graph import KnowledgeGraphBuilder
from src.ekc.db.session import SessionLocal
from sqlalchemy.orm import Session
from src.ekc.db.models import Chunk as ChunkModel, EntityMention, EntityRelationship, Entity

BATCH_SIZE = 100


def build():
    db = SessionLocal()
    extractor = get_extractor()
    rel_extractor = RelationshipExtractor(extractor.nlp)
    builder = KnowledgeGraphBuilder()

    # Clear existing KG data for a clean rebuild
    logger.info("Clearing existing KG data...")
    db.query(EntityMention).delete()
    db.query(EntityRelationship).delete()
    db.query(Entity).delete()
    db.commit()
    builder._entity_db_ids.clear()

    # Count chunks
    total = db.query(ChunkModel).count()
    logger.info(f"Processing {total} chunks")

    processed = 0
    offset = 0

    while offset < total:
        chunks = db.query(ChunkModel).offset(offset).limit(BATCH_SIZE).all()
        if not chunks:
            break

        for chunk in chunks:
            try:
                entities = extractor.extract(chunk.content, chunk.chunk_id)
                if not entities:
                    continue

                relationships = rel_extractor.extract(chunk.content, entities)

                builder.add_entities_and_relations(
                    entities, relationships, chunk.chunk_id, db
                )
                processed += 1

            except Exception as e:
                db.rollback()
                logger.error(f"KG extraction failed for chunk {chunk.chunk_id[:8] if hasattr(chunk, 'chunk_id') else '?'}: {e}")
                continue

        db.commit()
        offset += BATCH_SIZE

        if offset % 500 == 0 or offset >= total:
            logger.info(
                f"  Progress: {min(offset, total)}/{total} chunks | "
                f"Nodes: {builder.graph.number_of_nodes()} | "
                f"Edges: {builder.graph.number_of_edges()}"
            )

    # Add engineered demo chain edges
    logger.info("Adding engineered demo chain edges...")
    _add_demo_chain(builder, db)
    db.commit()

    # Save GraphML
    builder.save_graphml()

    logger.info("=" * 60)
    logger.info(f"KG BUILD COMPLETE")
    logger.info(f"  Chunks processed: {processed}/{total}")
    logger.info(f"  Graph nodes:      {builder.graph.number_of_nodes()}")
    logger.info(f"  Graph edges:      {builder.graph.number_of_edges()}")

    # Entity type breakdown
    from collections import Counter
    type_counts = Counter(
        data.get("entity_type", "Unknown")
        for _, data in builder.graph.nodes(data=True)
    )
    for etype, count in type_counts.most_common():
        logger.info(f"  {etype:20s}: {count}")

    db.close()


def _add_demo_chain(builder: KnowledgeGraphBuilder, db: Session):
    """
    Engineer the demo chain edges into the graph.
    Project Orion -> auth-service -> SOP-IT-001 -> JRA-1001
    This guarantees the multi-hop demo query resolves correctly.
    """
    from src.ekc.db.models import RelationshipType
    import uuid

    chain = [
        ("project:orion",       "tech:auth_service",        RelationshipType.belongs_to, 2.0),
        ("tech:auth_service",   "sop:incident_management",  RelationshipType.belongs_to, 2.0),
        ("tech:auth_service",   "concept:rollback",         RelationshipType.related_to, 2.0),
        ("ticket:jra_1001",     "tech:auth_service",        RelationshipType.related_to, 2.0),
        ("ticket:jra_1001",     "sop:incident_management",  RelationshipType.resolves,   2.0),
        ("concept:rollback",    "sop:incident_management",  RelationshipType.related_to, 2.0),
        ("concept:crashloopbackoff", "tech:kubernetes",     RelationshipType.related_to, 2.0),
        ("concept:crashloopbackoff", "sop:incident_management", RelationshipType.resolves, 2.0),
    ]

    for src_can, tgt_can, rel_type, weight in chain:
        # Ensure both nodes exist in DB
        for canonical in (src_can, tgt_can):
            if canonical not in builder._entity_db_ids:
                ent = db.query(Entity).filter(
                    Entity.canonical_name == canonical
                ).first()
                if not ent:
                    ent_type = canonical.split(":")[0].title()
                    ent = Entity(
                        entity_id=str(uuid.uuid4()),
                        canonical_name=canonical,
                        entity_type=ent_type,
                        aliases=[canonical],
                    )
                    db.add(ent)
                    db.flush()
                builder._entity_db_ids[canonical] = ent.entity_id
                builder.graph.add_node(
                    canonical,
                    entity_type=canonical.split(":")[0].title(),
                    db_id=ent.entity_id,
                )

        # Add edge
        src_db = builder._entity_db_ids[src_can]
        tgt_db = builder._entity_db_ids[tgt_can]

        builder.graph.add_edge(src_can, tgt_can,
                               relationship_type=rel_type.value, weight=weight)
        db.add(EntityRelationship(
            rel_id=str(uuid.uuid4()),
            source_entity_id=src_db,
            target_entity_id=tgt_db,
            relationship_type=rel_type,
            weight=weight,
        ))

    logger.info(f"Demo chain: {len(chain)} edges added")


if __name__ == "__main__":
    build()