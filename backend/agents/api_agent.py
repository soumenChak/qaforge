"""
QAForge -- API Testing Agent
==============================
Specialised QA agent for REST API / HTTP service testing.

Covers:
  - CRUD lifecycle (Create / Read / Update / Delete)
  - Authentication & authorization flows (JWT, API keys, OAuth)
  - Input validation (required fields, types, boundaries, XSS/injection)
  - Pagination, filtering, sorting, search
  - Error handling & status codes (4xx, 5xx)
  - Rate limiting & concurrency
  - Response schema & contract validation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.base_qa_agent import BaseQAAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain knowledge
# ---------------------------------------------------------------------------

_API_COMMON_PATTERNS = """\
=== API / HTTP SERVICE TESTING DOMAIN KNOWLEDGE ===

You are generating test cases for a REST API or HTTP-based service.
Apply the following domain expertise when constructing tests:

1. CRUD LIFECYCLE TESTING
   - Create (POST): validate 201 response, returned resource contains generated ID
   - Read (GET): verify resource exists, fields match what was created
   - Update (PUT/PATCH): change fields, verify persistence on subsequent GET
   - Delete (DELETE): verify 200/204 response, subsequent GET returns 404
   - Idempotency: duplicate POST with same data should fail or return existing
   - List (GET collection): verify pagination, total count, default ordering

2. AUTHENTICATION & AUTHORIZATION
   - Login flow: POST credentials → receive JWT/token → use in subsequent requests
   - Expired token: verify 401 when using expired or revoked token
   - Missing token: verify 401 when no Authorization header present
   - Wrong role: verify 403 when user lacks required role (RBAC)
   - Token refresh: verify refresh token flow if applicable
   - Concurrent sessions: verify behaviour with multiple active tokens

3. INPUT VALIDATION
   - Required fields missing: verify 422/400 with descriptive error
   - Wrong types: string where integer expected, null where required
   - Boundary values: max-length strings, min/max integers, empty arrays
   - Invalid formats: malformed email, phone, date, UUID
   - XSS/injection: HTML tags, script tags, SQL injection patterns
   - Unicode & special characters: emoji, accented chars, RTL text

4. PAGINATION, FILTERING & SEARCH
   - Default pagination: first page, default page size
   - Custom page size: verify limit/offset or page/per_page parameters
   - Out-of-bounds: page 9999 should return empty array, not error
   - Filtering: by status, date range, category — verify narrowed results
   - Sorting: asc/desc on different fields, verify order correctness
   - Search: full-text search, partial match, case sensitivity

5. ERROR HANDLING
   - 400 Bad Request: malformed JSON, invalid Content-Type
   - 404 Not Found: non-existent resource ID, wrong endpoint path
   - 409 Conflict: duplicate unique constraint (email, username)
   - 422 Unprocessable: valid JSON but fails business rules
   - 429 Too Many Requests: rate limit exceeded
   - 500 Internal Server Error: verify doesn't leak stack traces

6. RESPONSE CONTRACT
   - Required fields always present in response
   - Correct data types (string, int, float, boolean, null)
   - Consistent date/time formats (ISO 8601)
   - HATEOAS links if applicable
   - Content-Type header matches response body
   - Response time within acceptable threshold (< 2s for CRUD, < 5s for reports)

7. EDGE CASES
   - Empty database: GET collection returns empty array, not error
   - Concurrent modifications: two simultaneous updates to same resource
   - Large payloads: request body at max allowed size
   - Special characters in URL path parameters
   - Trailing slashes: /api/users vs /api/users/
"""

_FASTAPI_PATTERNS = """\
=== FASTAPI-SPECIFIC PATTERNS ===
- Auto-generated OpenAPI spec at /openapi.json or /docs
- Pydantic validation returns 422 with detail array [{loc, msg, type}]
- Dependency injection for auth: Depends(get_current_user)
- Path parameters: /api/items/{item_id} with UUID or int
- Query parameters: ?skip=0&limit=10 for pagination
- Request body validated via Pydantic model
- Async endpoints: consider concurrent request testing
- HTTPException patterns: status_code + detail string
"""

_GENERIC_REST_PATTERNS = """\
=== GENERIC REST API PATTERNS ===
- Standard HTTP verbs: GET (read), POST (create), PUT/PATCH (update), DELETE (remove)
- Resource naming: plural nouns (/users, /orders, /products)
- Nested resources: /users/{id}/orders
- Status codes: 200 OK, 201 Created, 204 No Content, 400/401/403/404/422/500
- Content negotiation: Accept and Content-Type headers
- Versioning: /v1/users or Accept: application/vnd.api+json;version=1
"""


class APIAgent(BaseQAAgent):
    """
    API Testing Agent -- generates test cases for REST APIs and
    HTTP-based services with deep knowledge of common API patterns.
    """

    SUB_DOMAIN_FASTAPI = "fastapi"
    SUB_DOMAIN_GENERIC = "generic"

    # Use higher token budget for detailed API test steps
    DEFAULT_MAX_TOKENS: int = 8192

    def __init__(
        self,
        sub_domain: str = SUB_DOMAIN_GENERIC,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.sub_domain = sub_domain.lower().strip()
        logger.info("APIAgent initialised. sub_domain=%s", self.sub_domain)

    def get_domain_patterns(self) -> str:
        """Return API testing domain knowledge for prompt injection."""
        patterns = _API_COMMON_PATTERNS

        if self.sub_domain == self.SUB_DOMAIN_FASTAPI:
            patterns += "\n" + _FASTAPI_PATTERNS
        else:
            patterns += "\n" + _GENERIC_REST_PATTERNS

        return patterns

    def generate_test_cases(
        self,
        description: str,
        context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate API-focused test cases.

        Args:
            description: The API requirement / feature description.
            context: Additional context (app profile, KB, requirements).
            config: Optional overrides (count, temperature, etc.).

        Returns:
            List of test-case dicts with execution_type="api".
        """
        config = config or {}
        count = config.get("count", 10)
        examples = config.get("example_test_cases")

        domain_patterns = self.get_domain_patterns()

        prompt = self.build_prompt(
            description=description,
            context=context,
            domain_patterns=domain_patterns,
            additional_context=config.get("additional_context", ""),
            example_test_cases=examples,
            count=count,
        )

        provider_config = {
            k: v for k, v in config.items()
            if k in ("max_tokens", "temperature", "model")
        }
        response = self._call_llm(prompt, provider_config)

        test_cases = self._parse_response(response.text)

        # Tag with API domain
        for tc in test_cases:
            tags = tc.get("domain_tags", [])
            if "api" not in [t.lower() for t in tags]:
                tags.append("API")
            tc["domain_tags"] = tags
            # Ensure execution_type is api
            if not tc.get("execution_type"):
                tc["execution_type"] = "api"

        logger.info(
            "APIAgent generated %d test cases (requested %d) | tokens_in=%d tokens_out=%d",
            len(test_cases), count, response.tokens_in, response.tokens_out,
        )
        return test_cases
