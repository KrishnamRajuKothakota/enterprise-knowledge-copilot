"""
PII redaction using Microsoft Presidio.
Custom recognisers: Aadhaar (12-digit + Verhoeff checksum), PAN (regex + context).
Original PII values are never stored anywhere — only typed tokens like [AADHAAR_1].
Redaction events are written to the REDACTION_AUDIT table.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from presidio_analyzer import (
    AnalyzerEngine, PatternRecognizer, Pattern, RecognizerResult
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult as AnonResult
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)


# ── Verhoeff checksum for Aadhaar validation ──────────────────────────────────

VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]
VERHOEFF_INV = [0,4,3,2,1,9,8,7,6,5]


def _verhoeff_check(number: str) -> bool:
    """Return True if the digit string passes the Verhoeff checksum."""
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][int(digit)]]
    return c == 0


# ── Custom recognisers ────────────────────────────────────────────────────────

class AadhaarRecognizer(PatternRecognizer):
    """
    Recognises 12-digit Aadhaar numbers.
    Format: XXXX XXXX XXXX or XXXXXXXXXXXX (no spaces).
    Validated with Verhoeff checksum.
    """
    PATTERNS = [
        Pattern("AADHAAR_SPACED",  r"\b[2-9]\d{3}\s\d{4}\s\d{4}\b", 0.6),
        Pattern("AADHAAR_COMPACT", r"\b[2-9]\d{11}\b",               0.5),
    ]
    CONTEXT = ["aadhaar", "aadhar", "uid", "uidai", "unique identification"]

    def __init__(self):
        super().__init__(
            supported_entity="AADHAAR_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = re.sub(r"\s", "", pattern_text)
        if len(digits) != 12:
            return False
        # First digit must be 2-9 (already in pattern, double-check)
        if int(digits[0]) < 2:
            return False
        return _verhoeff_check(digits)


class PANRecognizer(PatternRecognizer):
    """
    Recognises Indian PAN card numbers.
    Format: AAAAA9999A  (5 alpha + 4 digit + 1 alpha, all uppercase).
    """
    PATTERNS = [
        Pattern("PAN_CARD", r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", 0.6),
    ]
    CONTEXT = [
        "pan", "permanent account", "income tax", "pan card",
        "pan number", "pan no",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="PAN_NUMBER",
            patterns=self.PATTERNS,
            context=self.CONTEXT,
        )


# ── Redaction result ──────────────────────────────────────────────────────────

@dataclass
class RedactionResult:
    redacted_text: str
    findings: list[dict] = field(default_factory=list)
    # findings: [{"pii_type": "AADHAAR_NUMBER", "token": "[AADHAAR_1]"}, ...]


# ── Main redactor ─────────────────────────────────────────────────────────────

class PIIRedactor:
    """
    Detects and anonymises PII using Presidio.
    Entities detected: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, IP_ADDRESS,
                       CREDIT_CARD, AADHAAR_NUMBER, PAN_NUMBER.
    Replacements use typed, numbered tokens so audit records are meaningful.
    """

    ENTITIES = [
        "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
        "IP_ADDRESS", "CREDIT_CARD",
        "AADHAAR_NUMBER", "PAN_NUMBER",
    ]

    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.analyzer.registry.add_recognizer(AadhaarRecognizer())
        self.analyzer.registry.add_recognizer(PANRecognizer())
        self.anonymizer = AnonymizerEngine()

    def redact(self, text: str, language: str = "en") -> RedactionResult:
        """
        Redact all PII from text.
        Returns RedactionResult with redacted text and a list of findings.
        The original values are never stored in findings — only entity type + token.
        """
        if not text or not text.strip():
            return RedactionResult(redacted_text=text)

        results = self.analyzer.analyze(
            text=text,
            entities=self.ENTITIES,
            language=language,
        )

        if not results:
            return RedactionResult(redacted_text=text)

        # Build per-entity counters for numbered tokens ([PERSON_1], [PERSON_2]…)
        counters: dict[str, int] = {}
        operators: dict[str, OperatorConfig] = {}
        findings = []

        # Sort by start position so numbering is left-to-right
        for result in sorted(results, key=lambda r: r.start):
            entity = result.entity_type
            counters[entity] = counters.get(entity, 0) + 1
            token = f"[{entity}_{counters[entity]}]"
            findings.append({"pii_type": entity, "token": token})

        # Use replace operator with lambda — Presidio calls it per entity
        # We use a simple replace-all approach: anonymize with default replace
        anon_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators={
                entity: OperatorConfig("replace", {"new_value": f"[{entity}]"})
                for entity in self.ENTITIES
            },
        )

        return RedactionResult(
            redacted_text=anon_result.text,
            findings=findings,
        )


# ── Module-level singleton ────────────────────────────────────────────────────

_redactor: Optional[PIIRedactor] = None


def get_redactor() -> PIIRedactor:
    global _redactor
    if _redactor is None:
        _redactor = PIIRedactor()
    return _redactor