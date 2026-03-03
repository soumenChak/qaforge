"""
QAForge -- Data Engineering Testing Agent
===========================================
Specialised QA agent for Data Engineering and Migration testing,
with deep knowledge of Snowflake, Databricks, Oracle, and ETL patterns.

Covers:
  - Count reconciliation (source vs target)
  - Duplicate detection
  - Null / PK validation
  - Schema validation and data type mapping
  - SCD Type 2 verification
  - Incremental / delta load testing
  - Data quality checks
  - ETL pipeline validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.base_qa_agent import BaseQAAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain knowledge blocks
# ---------------------------------------------------------------------------

_DE_COMMON_PATTERNS = """\
=== DATA ENGINEERING TESTING DOMAIN KNOWLEDGE ===

You are generating test cases for a Data Engineering / Migration project.
Apply the following domain expertise when constructing tests:

1. COUNT RECONCILIATION
   - Compare row counts between source and target tables
   - Use: SELECT COUNT(*) FROM source vs SELECT COUNT(*) FROM target
   - Tolerance: typically 0% for full loads, configurable for incremental
   - Compare with WHERE clauses for filtered/partitioned loads
   - Track count over time for trend analysis

2. DUPLICATE DETECTION
   - Check primary key uniqueness: GROUP BY pk HAVING COUNT(*) > 1
   - Check composite key uniqueness for tables with multi-column PKs
   - Check business key uniqueness (natural keys)
   - Detect duplicates introduced by ETL transformation errors

3. NULL / PRIMARY KEY VALIDATION
   - Verify no null values in primary key columns
   - Use: SELECT COUNT(*) FROM target WHERE pk IS NULL
   - Verify NOT NULL constraints on mandatory columns
   - Check for empty strings masquerading as values

4. SCHEMA VALIDATION
   - Compare column names between source and target
   - Verify data type mapping (e.g. Oracle NUMBER → Databricks DECIMAL)
   - Check column order if relevant
   - Verify new columns added and deprecated columns removed
   - Use INFORMATION_SCHEMA.COLUMNS or DESCRIBE TABLE

5. DATA TYPE MAPPING VERIFICATION
   - Oracle NUMBER(p,s) → Databricks DECIMAL(p,s)
   - Oracle VARCHAR2 → Databricks STRING
   - Oracle DATE → Databricks TIMESTAMP
   - Oracle CLOB → Databricks STRING
   - Handle precision loss scenarios

6. SAMPLE DATA COMPARISON
   - Compare sample rows between source and target
   - Use MINUS/EXCEPT for set difference
   - Hash-based comparison for large datasets
   - Column-by-column value comparison for critical fields

7. AGGREGATE RECONCILIATION
   - Compare SUM, AVG, MIN, MAX on numeric columns
   - Verify distribution consistency
   - Check boundary values preserved

8. DATA FRESHNESS
   - Verify MAX(load_timestamp) is within expected window
   - Check no stale partitions
   - Validate incremental load picked up recent changes

9. SCD TYPE 2 VALIDATION
   - Verify effective_date, end_date, is_current flag logic
   - Verify historical records preserved on update
   - Verify only one active record per business key
   - Test: UPDATE source → target should create new version with is_current=true

10. INCREMENTAL / DELTA LOAD
    - Verify only new/changed records loaded
    - Verify deletes handled correctly (soft delete vs hard delete)
    - Verify unchanged records not duplicated
    - Watermark/checkpoint validation
"""

_DE_ENTERPRISE_FORMAT = """\
=== ENTERPRISE DATA ENGINEERING TEST CASE FORMAT ===

Generate test cases following this EXACT enterprise format:

STRUCTURE RULES:
- Each test case MUST have 2-6 DETAILED steps
- Steps MUST reference SPECIFIC table names, column names from the requirement
- SQL steps MUST include the actual SQL query in the sql_script field
- Prerequisites MUST list system access needed
- test_data MUST include: source_table, target_table, primary_key, and any relevant column names

STEP TYPES FOR DE:
- "snowflake" — Query Snowflake tables. ALWAYS include sql_script.
- "databricks" — Query Databricks tables. ALWAYS include sql_script.
- "oracle" — Query Oracle source. ALWAYS include sql_script.
- "sql" — Generic SQL (when platform not specified). ALWAYS include sql_script.
- "data_validation" — Compare values from previous steps (counts, sums, schemas)
- "manual" — Manual verification steps

SQL SCRIPT REQUIREMENTS:
- Use actual table and column names from the requirement
- Include fully qualified names (schema.table) where possible
- Use parameterised placeholders ({{source_table}}, {{target_table}}) when names are generic
- Include WHERE clauses for filtered scenarios
- Include ORDER BY for deterministic comparisons

TEST CASE CATEGORIES TO COVER:
1. Count Validation — Row count source vs target
2. Duplicate Detection — PK uniqueness in target
3. Null PK Validation — No nulls in primary key
4. Schema Validation — Column names and data types match
5. Data Comparison — Sample data matches between systems
6. Aggregate Validation — SUM/AVG/MIN/MAX reconciliation
7. Freshness Check — Data loaded within expected window
8. SCD Type 2 — Historical versioning correct
9. Incremental Load — Only changed records processed
10. Data Quality — Format validation, referential integrity

EXAMPLE FULL TEST CASE:
{
  "test_case_id": "TC-DE-001",
  "title": "Count of records validation",
  "description": "Verify whether the count of records in source table matches target table after migration",
  "preconditions": "1. User should have access to source and target databases",
  "test_steps": [
    {
      "step_number": 1,
      "action": "Navigate to source database and query the table to get the count of records",
      "expected_result": "User should be able to get the count of records from source",
      "step_type": "oracle",
      "sql_script": "SELECT COUNT(*) AS SOURCE_COUNT FROM de_qa.orc_xyz;",
      "system": "Oracle"
    },
    {
      "step_number": 2,
      "action": "Navigate to target database and query the table to get the count of records",
      "expected_result": "User should be able to get the count of records from target",
      "step_type": "databricks",
      "sql_script": "SELECT COUNT(*) AS TARGET_COUNT FROM de_qa.odp_xyz;",
      "system": "Databricks"
    },
    {
      "step_number": 3,
      "action": "Compare the count of records between source and target tables",
      "expected_result": "The count of records should match between source and target",
      "step_type": "data_validation",
      "system": "Cross-system"
    }
  ],
  "expected_result": "Row counts match between source and target tables",
  "priority": "High",
  "category": "Migration",
  "domain_tags": ["Data Engineering", "Migration", "Count Validation"],
  "test_data": {"source_table": "de_qa.orc_xyz", "target_table": "de_qa.odp_xyz", "primary_key": "primary_key_column"},
  "execution_type": "sql"
}
"""

_SNOWFLAKE_PATTERNS = """\
=== SNOWFLAKE-SPECIFIC PATTERNS ===
- VARIANT/OBJECT/ARRAY columns for semi-structured data
- FLATTEN function for exploding arrays/objects
- TIME_TRAVEL for historical data queries (AT/BEFORE)
- CLONE for zero-copy test data setup
- STREAMS for CDC (change data capture) validation
- TASKS for scheduled pipeline testing
- INFORMATION_SCHEMA for metadata queries
- Transient/temporary tables for test isolation
- COPY INTO for bulk load validation
- MERGE statement for upsert testing
- Clustering keys and micro-partition pruning
- External stages (S3/Azure/GCS) for source data
"""

_DATABRICKS_PATTERNS = """\
=== DATABRICKS-SPECIFIC PATTERNS ===
- Delta Lake: ACID transactions, time travel (DESCRIBE HISTORY)
- Unity Catalog: three-level namespace (catalog.schema.table)
- Delta Live Tables (DLT) pipeline testing
- Spark SQL vs PySpark DataFrame operations
- OPTIMIZE and VACUUM for table maintenance
- Schema evolution (mergeSchema, overwriteSchema)
- Auto Loader for incremental ingestion testing
- Medallion architecture: bronze → silver → gold validation
- dbutils for notebook testing patterns
- Widget parameters for parameterised testing
"""

_ORACLE_PATTERNS = """\
=== ORACLE SOURCE PATTERNS ===
- Sequences and auto-increment validation after migration
- Synonyms: verify correct object resolution
- DBLinks: cross-database query validation
- Materialised views: refresh and data consistency
- PL/SQL stored procedures: output validation
- Oracle-specific data types: NUMBER, VARCHAR2, DATE, CLOB, BLOB
- Data dictionary queries: ALL_TABLES, ALL_TAB_COLUMNS, ALL_CONSTRAINTS
- Partitioned tables: partition-level count validation
- Triggers: verify trigger logic migrated or replicated
"""


class DEAgent(BaseQAAgent):
    """
    Data Engineering Testing Agent — generates test cases specialised
    for data migration, ETL/ELT pipelines, and warehouse validation.

    Supports sub-domains: snowflake, databricks, oracle, generic.
    Produces enterprise-grade test cases with embedded SQL scripts.
    """

    # Enterprise TCs with SQL scripts need more tokens
    DEFAULT_MAX_TOKENS: int = 8192

    # Sub-domain identifiers
    SUB_DOMAIN_SNOWFLAKE = "snowflake"
    SUB_DOMAIN_DATABRICKS = "databricks"
    SUB_DOMAIN_ORACLE = "oracle"
    SUB_DOMAIN_GENERIC = "generic"

    def __init__(
        self,
        sub_domain: str = SUB_DOMAIN_GENERIC,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.sub_domain = sub_domain.lower().strip()
        logger.info("DEAgent initialised. sub_domain=%s", self.sub_domain)

    def get_domain_patterns(self) -> str:
        """
        Return DE-specific domain knowledge for prompt injection.

        Combines common DE patterns with sub-domain-specific patterns
        plus enterprise format instructions.
        """
        patterns = _DE_COMMON_PATTERNS

        if self.sub_domain == self.SUB_DOMAIN_SNOWFLAKE:
            patterns += "\n" + _SNOWFLAKE_PATTERNS
        elif self.sub_domain == self.SUB_DOMAIN_DATABRICKS:
            patterns += "\n" + _DATABRICKS_PATTERNS
        elif self.sub_domain == self.SUB_DOMAIN_ORACLE:
            patterns += "\n" + _ORACLE_PATTERNS
        else:
            # Generic: include highlights from all platforms
            patterns += (
                "\n=== GENERIC DATA ENGINEERING ===\n"
                "Apply general data engineering testing patterns. If the requirement "
                "mentions a specific platform (Snowflake, Databricks, Oracle, BigQuery, "
                "etc.), tailor the test cases to that platform's SQL dialect and features."
            )

        # Always include enterprise format instructions
        patterns += "\n" + _DE_ENTERPRISE_FORMAT

        return patterns

    def generate_test_cases(
        self,
        description: str,
        context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate Data Engineering focused test cases.

        Args:
            description: The DE requirement / migration spec description.
            context: Additional context (e.g. from knowledge base).
            config: Optional overrides (count, sub_domain, temperature, etc.).

        Returns:
            List of test-case dicts with embedded SQL scripts.
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

        # Tag with DE domain
        for tc in test_cases:
            tags = tc.get("domain_tags", [])
            if "data engineering" not in [t.lower() for t in tags]:
                tags.append("Data Engineering")
            if self.sub_domain != self.SUB_DOMAIN_GENERIC:
                platform_tag = self.sub_domain.capitalize()
                if platform_tag.lower() not in [t.lower() for t in tags]:
                    tags.append(platform_tag)
            tc["domain_tags"] = tags

            # Default execution_type to sql for DE test cases
            if not tc.get("execution_type"):
                tc["execution_type"] = "sql"

        logger.info(
            "DEAgent generated %d test cases (requested %d) | tokens_in=%d tokens_out=%d",
            len(test_cases), count, response.tokens_in, response.tokens_out,
        )
        return test_cases

    @property
    def last_response_meta(self) -> Dict[str, Any]:
        return {"sub_domain": self.sub_domain}
