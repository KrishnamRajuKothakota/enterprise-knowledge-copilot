"""
NetworkX DiGraph builder.
- Builds in-memory DiGraph from extracted entities + relationships
- Persists to GraphML file
- Mirrors to Postgres ENTITY / ENTITY_MENTION / ENTITY_RELATIONSHIP tables
"""
import os
import logging
import networkx as nx
from sqlalchemy.orm import Session
from src.ekc.kg.extract import ExtractedEntity
from src.ekc.kg.relations import ExtractedRelationship
from src.ekc.db.models import Entity, EntityMention, EntityRelationship
from src.ekc.core.config import settings
import uuid

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:

    def __init__(self):
        self.graph = nx.DiGraph()
        # entity canonical_id -> db UUID
        self._entity_db_ids: dict[str, str] = {}

    def add_entities_and_relations(
        self,
        entities: list[ExtractedEntity],
        relationships: list[ExtractedRelationship],
        chunk_id: str,
        db: Session,
    ):
        """
        Add entities and relationships from one chunk to the graph and DB.
        Upserts entities (creates if not exists), always creates mentions.
        """
        # Upsert entities
        for ent in entities:
            if ent.canonical_id not in self._entity_db_ids:
                # Check DB first (resumable builds)
                db_ent = db.query(Entity).filter(
                    Entity.canonical_name == ent.canonical_id
                ).first()

                if not db_ent:
                    db_ent = Entity(
                        entity_id=str(uuid.uuid4()),
                        canonical_name=ent.canonical_id[:500],   # add [:500]
                        entity_type=ent.entity_type,
                        aliases=[ent.surface_form[:200]],        # add [:200]
                    )
                    db.add(db_ent)
                    db.flush()
                else:
                    # Add surface form to aliases if not already there
                    aliases = db_ent.aliases or []
                    if ent.surface_form not in aliases:
                        aliases.append(ent.surface_form)
                        db_ent.aliases = aliases

                self._entity_db_ids[ent.canonical_id] = db_ent.entity_id

                # Add node to NetworkX graph
                self.graph.add_node(
                    ent.canonical_id,
                    entity_type=ent.entity_type,
                    db_id=db_ent.entity_id,
                )

            # Always create a mention record for this chunk
            db.add(EntityMention(
                mention_id=str(uuid.uuid4()),
                entity_id=self._entity_db_ids[ent.canonical_id],
                chunk_id=chunk_id,
                confidence_score=0.85,
            ))

        # Add relationships
        for rel in relationships:
            src_db_id = self._entity_db_ids.get(rel.source_canonical)
            tgt_db_id = self._entity_db_ids.get(rel.target_canonical)

            if not src_db_id or not tgt_db_id:
                continue

            # Add edge to NetworkX graph
            self.graph.add_edge(
                rel.source_canonical,
                rel.target_canonical,
                relationship_type=rel.relationship_type.value,
                weight=rel.weight,
            )

            # Write to DB
            db.add(EntityRelationship(
                rel_id=str(uuid.uuid4()),
                source_entity_id=src_db_id,
                target_entity_id=tgt_db_id,
                relationship_type=rel.relationship_type,
                weight=rel.weight,
            ))

    def save_graphml(self):
        """Persist graph to GraphML file."""
        os.makedirs(os.path.dirname(settings.graph_path), exist_ok=True)
        nx.write_graphml(self.graph, settings.graph_path)
        logger.info(
            f"Graph saved: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges -> {settings.graph_path}"
        )

    def load_graphml(self):
        """Load graph from GraphML file."""
        if os.path.exists(settings.graph_path):
            self.graph = nx.read_graphml(settings.graph_path)
            logger.info(
                f"Graph loaded: {self.graph.number_of_nodes()} nodes, "
                f"{self.graph.number_of_edges()} edges"
            )

    @property
    def stats(self) -> dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "entity_types": dict(
                nx.get_node_attributes(self.graph, "entity_type")
            ),
        }