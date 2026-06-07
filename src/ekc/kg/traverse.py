"""
2-hop graph traversal for knowledge graph retrieval.
Given a query, extracts entities, anchors them to graph nodes,
traverses up to 2 hops, and returns chunk_ids via ENTITY_MENTION.
"""
import logging
from sqlalchemy.orm import Session
from src.ekc.kg.extract import get_extractor
from src.ekc.kg.alias import resolve, get_canonical
from src.ekc.db.models import Entity, EntityMention, EntityRelationship
from src.ekc.core.config import settings

logger = logging.getLogger(__name__)


class GraphTraverser:

    def __init__(self, db: Session):
        self.db = db

    def retrieve(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Extract entities from query -> anchor to graph ->
        2-hop traversal -> return (chunk_id, score) pairs.
        """
        # Extract entities from query
        extractor = get_extractor()
        query_entities = extractor.extract(query)

        if not query_entities:
            # Fallback: try direct alias lookup on query tokens
            query_entities = self._token_lookup(query)

        if not query_entities:
            logger.debug("Graph retrieval: no entities found in query")
            return []

        canonical_ids = list({e.canonical_id for e in query_entities})
        logger.debug(f"Graph retrieval anchors: {canonical_ids}")

        # Find anchor entity DB records
        anchor_db_ids = []
        for canonical in canonical_ids:
            ent = self.db.query(Entity).filter(
                Entity.canonical_name == canonical
            ).first()
            if ent:
                anchor_db_ids.append(ent.entity_id)

        if not anchor_db_ids:
            logger.debug("Graph retrieval: no anchor entities in DB")
            return []

        # Collect entity IDs reachable within 2 hops
        reachable_ids = set(anchor_db_ids)

        # Hop 1: direct neighbours
        hop1 = self.db.query(EntityRelationship).filter(
            EntityRelationship.source_entity_id.in_(anchor_db_ids)
        ).all()
        hop1_ids = {r.target_entity_id for r in hop1}
        reachable_ids.update(hop1_ids)

        # Hop 2: neighbours of neighbours
        if hop1_ids:
            hop2 = self.db.query(EntityRelationship).filter(
                EntityRelationship.source_entity_id.in_(hop1_ids)
            ).all()
            reachable_ids.update(r.target_entity_id for r in hop2)

        logger.debug(f"Graph traversal: {len(reachable_ids)} reachable entities")

        # Get chunk_ids via ENTITY_MENTION
        mentions = self.db.query(EntityMention).filter(
            EntityMention.entity_id.in_(reachable_ids)
        ).all()

        # Score: anchor mentions score higher than traversed ones
        chunk_scores: dict[str, float] = {}
        for mention in mentions:
            is_anchor = mention.entity_id in set(anchor_db_ids)
            score = 1.0 if is_anchor else 0.6
            # Take highest score per chunk
            chunk_scores[mention.chunk_id] = max(
                chunk_scores.get(mention.chunk_id, 0.0),
                score,
            )

        # Sort by score, return top_k
        results = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _token_lookup(self, query: str) -> list:
        """
        Fallback: split query into tokens and look up each in alias map.
        Returns mock ExtractedEntity-like objects for any matches.
        """
        from src.ekc.kg.extract import ExtractedEntity
        from src.ekc.kg.alias import get_canonical

        found = []
        tokens = query.lower().split()
        # Try bigrams and unigrams
        for i in range(len(tokens)):
            for j in range(i + 1, min(i + 4, len(tokens) + 1)):
                phrase = " ".join(tokens[i:j])
                canonical = get_canonical(phrase)
                if canonical:
                    found.append(ExtractedEntity(
                        surface_form=phrase,
                        canonical_id=canonical,
                        entity_type="Unknown",
                        start=0, end=0,
                    ))
        return found