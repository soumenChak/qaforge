"""
QAForge -- MDM Testing Agent
==============================
Specialised QA agent for Master Data Management (MDM) platforms,
with deep knowledge of Reltio and Semarchy testing patterns.

Covers:
  - Match rule testing (exact, fuzzy, phonetic, weighted scoring)
  - Survivorship / golden record assembly
  - Data quality (null checks, format validation, referential integrity)
  - Cross-reference / crosswalk validation
  - Real-time sync and initial load testing
  - Merge / unmerge scenarios
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.base_qa_agent import BaseQAAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain knowledge blocks
# ---------------------------------------------------------------------------

_MDM_COMMON_PATTERNS = """\
=== MDM TESTING DOMAIN KNOWLEDGE ===

You are generating test cases for a Master Data Management (MDM) system.
Apply the following domain expertise when constructing tests:

1. MATCH RULE TESTING
   - Exact match: verify fields match character-for-character (case sensitivity, trim)
   - Fuzzy match: test Jaro-Winkler, Levenshtein, Soundex, NYSIIS thresholds
   - Phonetic match: verify phonetic encoding produces correct groupings
   - Weighted scoring: test composite score thresholds, tie-breaking, score decay
   - False positive / negative: deliberately craft records that should NOT match
   - Match group formation: verify transitive closure vs pairwise-only grouping
   - Match rule ordering and short-circuiting

2. SURVIVORSHIP / GOLDEN RECORD ASSEMBLY
   - Trust-based survivorship: source priority, confidence scores
   - Recency-based: most recent value wins (timestamp comparisons)
   - Source priority: canonical source overrides others
   - Field-level survivorship: different rules per attribute
   - Null handling: null should never overwrite a non-null trusted value
   - Conflict resolution: when two trusted sources disagree
   - Golden record completeness: ensure all survivorship fields populate

3. DATA QUALITY
   - Null / empty checks on mandatory fields
   - Format validation: phone, email, postal code, date formats
   - Referential integrity: foreign keys, parent-child relationships
   - Standardisation: address, name, phone normalisation
   - Duplicate detection vs duplicate prevention
   - Data profiling validation: uniqueness, completeness, conformity

4. CROSS-REFERENCE / CROSSWALK VALIDATION
   - Source-to-master mapping integrity
   - Bidirectional crosswalk lookups
   - Orphan detection (crosswalk to deleted master)
   - Crosswalk cardinality (1:1, N:1, 1:N)

5. REAL-TIME SYNC TESTING
   - Latency: record create/update propagation time
   - Ordering: out-of-order event handling
   - Idempotency: replayed events should not create duplicates
   - Error handling: API failures, timeouts, retries
   - Bulk vs real-time conflict resolution

6. INITIAL LOAD VALIDATION
   - Record count reconciliation (source vs MDM)
   - Data transformation accuracy
   - Match execution on load: expected merge count
   - Rejected record handling and error reports
   - Incremental load after initial

7. MERGE / UNMERGE SCENARIOS
   - Auto-merge: records above threshold merge without review
   - Manual merge: records in review queue, steward action
   - Unmerge: split previously merged records, restore original values
   - Merge cascade: downstream system notifications
   - Merge audit trail: who merged, when, which fields changed
"""

_RELTIO_PATTERNS = """\
=== RELTIO-SPECIFIC PATTERNS ===
- Match groups and L1/L2 match rules configuration
- L1 rules: blocking / candidate selection (fast, broad)
- L2 rules: detailed comparison (weighted scoring, thresholds)
- Cleanse functions: pre-match data cleansing (trim, uppercase, phonetic)
- Crosswalks: source-system-to-entity URI mapping
- Reltio match API: POST /entities/{id}/matches
- Potential matches queue: review, merge, reject actions
- Survivorship model: OvS (Overwrite by Source), MRV (Most Recent Value), custom
- Relations and interaction entities
- Tenant configuration and role-based access
- Data model: entity types, attributes, nested objects
- Real-time change data capture via webhooks
- Activity log validation for audit compliance

=== RELTIO ENTITY LOAD TESTING PATTERNS ===
- Entity load from Snowflake landing tables to Reltio
- Verify entity count in Reltio matches source count in Snowflake
- Verify attribute mapping: source column → Reltio attribute (Name, ID, Display Name, etc.)
- Verify nested attributes are present/absent as per spec (e.g. Image fields excluded)
- Verify crosswalk URIs generated correctly from source system keys
- Advanced Search in Reltio UI: filter by entity type + source system

=== RELTIO RELATION LOAD TESTING PATTERNS ===
- Relation load from landing tables with IS_DELETED flag handling
- Active relations (IS_DELETED=false): relation should be active in Reltio
- Inactive relations (IS_DELETED=true): relation should have delete date in crosswalk
- Relation attributes: verify values transferred (e.g. Premiere Airing Network = Yes/No)
- Relationship Tab navigation in Reltio UI: filter by relation type
- Cardinality validation: only one relation per entity should have a particular flag value

=== RELTIO ODL (OPERATIONAL DATA LOAD) TESTING ===
- Flag value changes: e.g. premiere network switches from one relation to another
- New relation addition: new record in landing table → new relation in Reltio
- Relation inactivation: IS_DELETED set to true → relation end-dated in Reltio
- Relation reactivation: IS_DELETED set back to false → relation reactivated
- LAST_MODIFIED_DATE tracking for changed records
- Verify only changed records are processed (delta/incremental load)

=== RELTIO RDM (REFERENCE DATA MANAGEMENT) ===
- RDM lookup tables loaded from source data
- Navigate to RDM in Reltio UI: Applications icon → RDM → verify lookup exists
- Crosswalk value calculation: canonical value → lowercase + remove spaces
- RDM table count matches source reference data count
"""

_SEMARCHY_PATTERNS = """\
=== SEMARCHY-SPECIFIC PATTERNS ===
- StewardX UI: review queue, merge/split actions, data stewardship
- Enrichers: pre-persist enrichers, post-persist enrichers, custom logic
- Match rules: fuzzy match, exact match, composite keys
- Merge rules: trust-based, recency, master/golden logic
- B2B model: organisation, contact, address hierarchy
- B2C model: customer, household, individual
- Publisher/subscriber pattern for data distribution
- Data quality dashboards and KPIs
- Batch processing: initial load, incremental load, delta detection
- Certification workflow: submit, review, certify, reject
- Integration layer: REST API, SOAP, file-based connectors
- Duplicate prevention vs duplicate detection modes
"""


_MDM_ENTERPRISE_FORMAT = """\
=== ENTERPRISE MDM TEST CASE FORMAT ===

Generate test cases following this EXACT enterprise format used by MDM consultancies:

STRUCTURE RULES:
- Each test case MUST have 4-10 DETAILED steps mixing different systems
- Steps MUST reference SPECIFIC table names, column names, entity types from the requirement
- Each step MUST have step_type to indicate which system it targets
- SQL steps MUST include the actual SQL query in the sql_script field
- Prerequisites MUST list ALL system access needed (e.g. "User should have access to Snowflake", "User should have access to Reltio")
- test_data MUST include structured metadata: source_table, target_entity_type, column_mappings if applicable

STEP TYPES FOR MDM:
- "snowflake" — Query Snowflake/source tables. ALWAYS include sql_script with actual SQL.
- "reltio_ui" — Navigate Reltio UI (login, Advanced Search, entity view, Relationship Tab, RDM).
    Include specific UI navigation instructions (e.g. "Navigate to Advanced Search, select entity type as Network, apply filter: Source System Name equals XXX")
- "reltio_api" — Call Reltio API endpoints (search, create, match, merge, config validation)
- "data_validation" — Compare data between systems (e.g. Snowflake count vs Reltio count, column A → Reltio field Name)
- "manual" — Manual steps (open spreadsheet, check reference data, visual comparison)

TEST CASE CATEGORIES TO COVER:
1. Schema/Table Changes — Verify DDL changes in landing tables (columns added/removed/renamed)
2. Entity Load Validation — Verify all entities loaded from source to Reltio with correct attributes
3. Relationship Load — Verify relations between entities (active, inactive with delete date)
4. Data Mapping — Verify specific source→target field mapping (Column A → Name, Column B → ID, etc.)
5. Count Reconciliation — Source record count in Snowflake matches entity count in Reltio
6. RDM/Lookup Validation — Verify reference data lookups loaded correctly
7. ODL/Incremental Changes — Delta load scenarios: flag changes, new relations, inactivation, reactivation
8. Data Quality — Cleansing, dedup, null handling, crosswalk transformation

EXAMPLE FULL TEST CASE:
{
  "test_case_id": "TC_SIT_001",
  "title": "Verify Network entity load to Reltio",
  "description": "Verify all Networks from the source spreadsheet are loaded to Reltio with correct attribute mapping",
  "preconditions": "1. User should have access to Reltio. 2. User should have access to Network spreadsheet (Reference Tab)",
  "test_steps": [
    {"step_number": 1, "action": "Login to Reltio MDM with valid credentials", "expected_result": "Login should be successful", "step_type": "reltio_ui", "system": "Reltio"},
    {"step_number": 2, "action": "Navigate to Advanced Search, select entity type as Network and apply filter: Source System Name equals XXX", "expected_result": "User should be able to fetch the records as per filter", "step_type": "reltio_ui", "system": "Reltio"},
    {"step_number": 3, "action": "Open the Network spreadsheet and refer columns A, B and C", "expected_result": "User should be able to view the data", "step_type": "manual", "system": "Spreadsheet"},
    {"step_number": 4, "action": "Ensure data is mapped from Spreadsheet to Reltio: Column A (Airing Network Name) to Name field, Column B (Network ID) to ID field, Column C (Network Display Name) to Display Name field", "expected_result": "Data should be mapped as expected", "step_type": "data_validation", "system": "Cross-system"},
    {"step_number": 5, "action": "Ensure Image related nested attributes (Images- Asset ID, Asset Type, URL) are not available in Reltio", "expected_result": "Image related nested attributes should not be available in Reltio", "step_type": "reltio_ui", "system": "Reltio"},
    {"step_number": 6, "action": "Verify the count of records in Spreadsheet matches with the count of Network entities in Reltio", "expected_result": "Counts should be matching", "step_type": "data_validation", "system": "Cross-system"}
  ],
  "expected_result": "All Network entities loaded to Reltio with correct attribute mapping and count matching source",
  "priority": "High",
  "category": "Functional",
  "domain_tags": ["MDM", "Reltio", "Entity Load"],
  "test_data": {"entity_type": "Network", "source": "Network spreadsheet", "column_mapping": {"Column A": "Name", "Column B": "ID", "Column C": "Display Name"}},
  "execution_type": "mdm"
}
"""


class MDMAgent(BaseQAAgent):
    """
    MDM Testing Agent -- generates test cases specialised for
    Master Data Management platforms (Reltio, Semarchy, generic MDM).

    Produces enterprise-grade multi-step test cases that mix SQL
    validation, MDM UI verification, and cross-system data comparison.
    """

    # Enterprise TCs are verbose (4-10 steps each) — need more tokens
    DEFAULT_MAX_TOKENS: int = 8192

    # Sub-domain identifiers
    SUB_DOMAIN_RELTIO = "reltio"
    SUB_DOMAIN_SEMARCHY = "semarchy"
    SUB_DOMAIN_GENERIC = "generic"

    def __init__(
        self,
        sub_domain: str = SUB_DOMAIN_GENERIC,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            sub_domain: One of "reltio", "semarchy", or "generic".
            **kwargs: Forwarded to BaseQAAgent (e.g. provider).
        """
        super().__init__(**kwargs)
        self.sub_domain = sub_domain.lower().strip()
        logger.info("MDMAgent initialised. sub_domain=%s", self.sub_domain)

    def get_domain_patterns(self) -> str:
        """
        Return MDM-specific domain knowledge for prompt injection.

        Combines common MDM patterns with sub-domain-specific patterns
        (Reltio or Semarchy) when applicable, plus enterprise format
        instructions for multi-step cross-system test cases.
        """
        patterns = _MDM_COMMON_PATTERNS

        if self.sub_domain == self.SUB_DOMAIN_RELTIO:
            patterns += "\n" + _RELTIO_PATTERNS
        elif self.sub_domain == self.SUB_DOMAIN_SEMARCHY:
            patterns += "\n" + _SEMARCHY_PATTERNS
        else:
            # Generic MDM: include highlights from both
            patterns += (
                "\n=== GENERIC MDM ===\n"
                "Apply general MDM testing patterns. If the requirement mentions "
                "a specific platform (Reltio, Semarchy, Informatica, etc.), tailor "
                "the test cases to that platform's terminology and patterns."
            )

        # Always include enterprise format instructions
        patterns += "\n" + _MDM_ENTERPRISE_FORMAT

        return patterns

    def generate_test_cases(
        self,
        description: str,
        context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate MDM-focused test cases.

        Args:
            description: The MDM requirement / feature description.
            context: Additional context (e.g. from knowledge base).
            config: Optional overrides:
                - count (int): number of test cases (default 10)
                - sub_domain (str): override the agent's sub_domain
                - temperature (float): LLM temperature
                - max_tokens (int): LLM max tokens
                - model (str): specific model to use
                - example_test_cases (list): few-shot examples

        Returns:
            List of test-case dicts.
        """
        config = config or {}
        count = config.get("count", 10)
        sub_domain_override = config.get("sub_domain")
        examples = config.get("example_test_cases")

        # Allow per-call sub_domain override
        if sub_domain_override:
            original = self.sub_domain
            self.sub_domain = sub_domain_override.lower().strip()
            domain_patterns = self.get_domain_patterns()
            self.sub_domain = original
        else:
            domain_patterns = self.get_domain_patterns()

        # Build the prompt
        prompt = self.build_prompt(
            description=description,
            context=context,
            domain_patterns=domain_patterns,
            additional_context=config.get("additional_context", ""),
            example_test_cases=examples,
            count=count,
        )

        # Call LLM
        provider_config = {
            k: v for k, v in config.items()
            if k in ("max_tokens", "temperature", "model")
        }
        response = self._call_llm(prompt, provider_config)

        # Parse and return
        test_cases = self._parse_response(response.text)

        # Tag with MDM domain
        for tc in test_cases:
            tags = tc.get("domain_tags", [])
            if "mdm" not in [t.lower() for t in tags]:
                tags.append("MDM")
            if self.sub_domain != self.SUB_DOMAIN_GENERIC:
                platform_tag = self.sub_domain.capitalize()
                if platform_tag.lower() not in [t.lower() for t in tags]:
                    tags.append(platform_tag)
            tc["domain_tags"] = tags

        logger.info(
            "MDMAgent generated %d test cases (requested %d) | tokens_in=%d tokens_out=%d",
            len(test_cases), count, response.tokens_in, response.tokens_out,
        )
        return test_cases

    @property
    def last_response_meta(self) -> Dict[str, Any]:
        """Metadata about the most recent LLM call (for pipeline tracking)."""
        # This is a lightweight approach; the orchestrator tracks full metadata
        return {"sub_domain": self.sub_domain}
