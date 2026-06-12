"""
Link SOP entities to their canonical IDs in the knowledge graph.
Creates explicit relationships between SOP documents and technology/team entities.
Run after build_kg.py to add SOP-level entity anchors.
Usage: python scripts/link_sop_entities.py
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from src.ekc.db.session import SessionLocal
from src.ekc.db.models import Entity, EntityRelationship, RelationshipType
import uuid

# SOP → Technology/Team entity mappings
# These links anchor SOP documents to their subject entities in the KG
SOP_ENTITY_LINKS = [
    ("sop:incident_management",    "tech:jira",          RelationshipType.related_to),
    ("sop:incident_management",    "tech:servicenow",    RelationshipType.related_to),
    ("sop:change_management",      "tech:jira",          RelationshipType.related_to),
    ("sop:vpn_access",             "tech:cisco_ise",     RelationshipType.related_to),
    ("sop:vpn_access",             "tech:vpn",           RelationshipType.related_to),
    ("sop:kubernetes_deployment",  "tech:kubernetes",    RelationshipType.related_to),
    ("sop:kubernetes_deployment",  "tech:docker",        RelationshipType.related_to),
    ("sop:patch_management",       "tech:linux",         RelationshipType.related_to),
    ("sop:access_provisioning",    "tech:okta",          RelationshipType.related_to),
    ("sop:access_provisioning",    "tech:active_directory", RelationshipType.related_to),
    ("sop:incident_management",    "tech:pagerduty",     RelationshipType.related_to),
    ("sop:backup_recovery",        "tech:aws_s3",        RelationshipType.related_to),
    ("sop:leaver_process",         "tech:okta",          RelationshipType.related_to),
    ("sop:leaver_process",         "tech:active_directory", RelationshipType.related_to),
    ("sop:onboarding",             "tech:okta",          RelationshipType.related_to),
    ("sop:onboarding",             "tech:jira",          RelationshipType.related_to),
]

def get_or_create_entity(db, canonical_name: str, entity_type: str = "SOP") -> Entity:
    """Get existing entity or create new one."""
    entity = db.query(Entity).filter(
        Entity.canonical_name == canonical_name
    ).first()
    if not entity:
        entity = Entity(
            entity_id=str(uuid.uuid4()),
            canonical_name=canonical_name,
            
            entity_type=entity_type,
            aliases=[canonical_name],
        )
        db.add(entity)
        db.flush()
        logger.info(f"  Created entity: {canonical_name} ({entity_type})")
    return entity

def main():
    db = SessionLocal()
    created_links = 0
    skipped = 0

    logger.info("Linking SOP entities to technology/team entities in KG...")

    for sop_name, tech_name, rel_type in SOP_ENTITY_LINKS:
        # Get or create both entities
        sop_type = "SOP" if sop_name.startswith("sop:") else "Technology"
        tech_type = "Technology"

        sop_entity = get_or_create_entity(db, sop_name, sop_type)
        tech_entity = get_or_create_entity(db, tech_name, tech_type)

        # Check if relationship already exists
        existing = db.query(EntityRelationship).filter(
            EntityRelationship.source_entity_id == sop_entity.entity_id,
            EntityRelationship.target_entity_id == tech_entity.entity_id,
            EntityRelationship.relationship_type == rel_type,
        ).first()

        if existing:
            skipped += 1
            continue

        # Create relationship
        rel = EntityRelationship(
            rel_id=str(uuid.uuid4()),
            source_entity_id=sop_entity.entity_id,
            target_entity_id=tech_entity.entity_id,
            relationship_type=rel_type,
            weight=1.0,
        )
        db.add(rel)
        created_links += 1

    db.commit()

    logger.info("=" * 50)
    logger.info("SOP ENTITY LINKING COMPLETE")
    logger.info(f"  Links created: {created_links}")
    logger.info(f"  Already existed: {skipped}")
    logger.info(f"  Total SOP mappings: {len(SOP_ENTITY_LINKS)}")
    logger.info("=" * 50)

    db.close()

if __name__ == "__main__":
    main()
