"""
Relationship extraction between entities.
Two strategies:
1. Co-occurrence within same chunk -> RELATED_TO
2. Dependency parse verb lemmas -> RESOLVES / BELONGS_TO
"""
import logging
import spacy
from dataclasses import dataclass
from src.ekc.kg.extract import ExtractedEntity
from src.ekc.db.models import RelationshipType

logger = logging.getLogger(__name__)

# Verb lemmas that signal specific relationship types
RESOLVES_VERBS   = {"resolve", "fix", "close", "address", "mitigate", "remediate", "solve"}
BELONGS_TO_VERBS = {"belong", "include", "contain", "cover", "apply", "govern", "follow"}


@dataclass
class ExtractedRelationship:
    source_canonical: str
    target_canonical: str
    relationship_type: RelationshipType
    weight: float = 1.0


class RelationshipExtractor:

    def __init__(self, nlp):
        self.nlp = nlp

    def extract(
        self,
        text: str,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedRelationship]:
        """
        Extract relationships between entities found in text.
        Returns deduplicated list of ExtractedRelationship.
        """
        if len(entities) < 2:
            return []

        relationships = []
        seen: set[tuple] = set()

        # Strategy 1: co-occurrence -> RELATED_TO for all entity pairs
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                if e1.canonical_id == e2.canonical_id:
                    continue
                key = (e1.canonical_id, e2.canonical_id, "RELATED_TO")
                if key not in seen:
                    seen.add(key)
                    relationships.append(ExtractedRelationship(
                        source_canonical=e1.canonical_id,
                        target_canonical=e2.canonical_id,
                        relationship_type=RelationshipType.related_to,
                        weight=1.0,
                    ))

        # Strategy 2: dependency parse for RESOLVES / BELONGS_TO
        try:
            doc = self.nlp(text[:50_000])
            canonical_map = {e.surface_form.lower(): e.canonical_id
                             for e in entities}

            for token in doc:
                if token.lemma_.lower() not in RESOLVES_VERBS | BELONGS_TO_VERBS:
                    continue

                rel_type = (
                    RelationshipType.resolves
                    if token.lemma_.lower() in RESOLVES_VERBS
                    else RelationshipType.belongs_to
                )

                # Find subject and object
                subj = next(
                    (c for c in token.children if c.dep_ in ("nsubj", "nsubjpass")),
                    None
                )
                obj = next(
                    (c for c in token.children if c.dep_ in ("dobj", "pobj", "attr")),
                    None
                )

                if not subj or not obj:
                    continue

                src_can = canonical_map.get(subj.text.lower())
                tgt_can = canonical_map.get(obj.text.lower())

                if src_can and tgt_can and src_can != tgt_can:
                    key = (src_can, tgt_can, rel_type.value)
                    if key not in seen:
                        seen.add(key)
                        relationships.append(ExtractedRelationship(
                            source_canonical=src_can,
                            target_canonical=tgt_can,
                            relationship_type=rel_type,
                            weight=1.5,  # higher weight for parsed relationships
                        ))
        except Exception as e:
            logger.debug(f"Dep-parse relationship extraction failed: {e}")

        return relationships