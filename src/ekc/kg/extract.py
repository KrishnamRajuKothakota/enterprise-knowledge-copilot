"""
Entity extraction using spaCy en_core_web_lg + custom EntityRuler.
Extracts: Technology, Project, Team, SOP, Ticket entity types.
PERSON entities are suppressed (DPDP compliance).
"""
import re
import logging
import spacy
from spacy.pipeline import EntityRuler
from dataclasses import dataclass
from src.ekc.kg.alias import resolve, get_canonical

logger = logging.getLogger(__name__)

# Entity type mapping from spaCy labels to our schema
SPACY_TO_OUR_TYPE = {
    "ORG":      "Team",
    "PRODUCT":  "Technology",
    "GPE":      "Technology",
    "LOC":      "Technology",
    "WORK_OF_ART": "Project",
    "EVENT":    "Project",
    "FAC":      "Technology",
}

# Suppressed types (DPDP compliance)
SUPPRESSED_TYPES = {"PERSON", "PER"}

# Custom IT-domain patterns for EntityRuler
CUSTOM_PATTERNS = [
    # SOP IDs
    {"label": "SOP_ID",    "pattern": [{"TEXT": {"REGEX": r"SOP-IT-\d{3}"}}]},
    # Jira ticket IDs
    {"label": "TICKET_ID", "pattern": [{"TEXT": {"REGEX": r"JRA-\d+"}}]},
    {"label": "TICKET_ID", "pattern": [{"TEXT": {"REGEX": r"INC\d+"}}]},
    {"label": "TICKET_ID", "pattern": [{"TEXT": {"REGEX": r"INC-\d+"}}]},
    # Priority labels
    {"label": "PRIORITY",  "pattern": [{"TEXT": {"REGEX": r"P[1-4]"}}]},
    # AWS services
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "ec2"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "s3"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "iam"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "eks"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "rds"}]},
    # Tech names
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "kubernetes"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "k8s"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "docker"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "terraform"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "ansible"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "jenkins"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "helm"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "nginx"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "redis"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "postgresql"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "postgres"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "prometheus"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "grafana"}]},
    {"label": "TECHNOLOGY","pattern": [{"LOWER": "auth-service"}]},
    # Teams
    {"label": "TEAM","pattern": [{"LOWER": "devops"}, {"LOWER": "team"}]},
    {"label": "TEAM","pattern": [{"LOWER": "l1"}, {"LOWER": "support"}]},
    {"label": "TEAM","pattern": [{"LOWER": "l2"}, {"LOWER": "support"}]},
    {"label": "TEAM","pattern": [{"LOWER": "platform"}, {"LOWER": "engineering"}]},
    {"label": "TEAM","pattern": [{"LOWER": "network"}, {"LOWER": "operations"}]},
    # Project Orion (demo chain)
    {"label": "PROJECT","pattern": [{"LOWER": "project"}, {"LOWER": "orion"}]},
    {"label": "PROJECT","pattern": [{"LOWER": "orion"}]},
    # ITSM concepts
    {"label": "CONCEPT","pattern": [{"LOWER": "sla"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "mttr"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "rca"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "cmdb"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "rollback"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "crashloopbackoff"}]},
        # SOP concepts for better query matching
    {"label": "CONCEPT","pattern": [{"LOWER": "vpn"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "escalation"}]},
    {"label": "CONCEPT","pattern": [{"LOWER": "onboarding"}]},
    {"label": "SOP_ID", "pattern": [{"LOWER": "incident"}, {"LOWER": "management"}]},
    {"label": "SOP_ID", "pattern": [{"LOWER": "vpn"}, {"LOWER": "access"}]},
    {"label": "SOP_ID", "pattern": [{"LOWER": "change"}, {"LOWER": "management"}]},
]

# Map custom labels to our entity types
CUSTOM_TO_OUR_TYPE = {
    "SOP_ID":    "SOP",
    "TICKET_ID": "Ticket",
    "TECHNOLOGY":"Technology",
    "TEAM":      "Team",
    "PROJECT":   "Project",
    "CONCEPT":   "Concept",
    "PRIORITY":  "Concept",
}


@dataclass
class ExtractedEntity:
    surface_form: str
    canonical_id: str
    entity_type: str
    start: int
    end: int


class EntityExtractor:

    def __init__(self):
        logger.info("Loading spaCy en_core_web_lg")
        self.nlp = spacy.load("en_core_web_lg")

        # Add EntityRuler before NER so custom patterns take priority
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(CUSTOM_PATTERNS)
        logger.info(f"EntityRuler: {len(CUSTOM_PATTERNS)} patterns loaded")

    def extract(self, text: str, chunk_id: str = "") -> list[ExtractedEntity]:
        """Extract entities from text, suppressing PERSON types."""
        if not text or not text.strip():
            return []

        # Truncate very long texts for spaCy (max 100k chars)
        doc = self.nlp(text[:100_000])
        entities = []
        seen_canonicals: set[str] = set()

        for ent in doc.ents:
            # Suppress PERSON (DPDP compliance)
            if ent.label_ in SUPPRESSED_TYPES:
                continue

            surface = ent.text.strip()
            if not surface or len(surface) < 2:
                continue

            if surface.startswith(("http://", "https://", "www.")):
                continue

            # Determine entity type
            our_type = (
                CUSTOM_TO_OUR_TYPE.get(ent.label_)
                or SPACY_TO_OUR_TYPE.get(ent.label_)
            )
            if not our_type:
                continue

            # Resolve to canonical ID
            canonical = resolve(surface)

            # Deduplicate within this chunk
            if canonical in seen_canonicals:
                continue
            seen_canonicals.add(canonical)

            entities.append(ExtractedEntity(
                surface_form=surface,
                canonical_id=canonical,
                entity_type=our_type,
                start=ent.start_char,
                end=ent.end_char,
            ))

        return entities


# ── Module-level singleton ────────────────────────────────────────────────────

_extractor = None


def get_extractor() -> EntityExtractor:
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor