"""
QAForge -- Executable Test Generator
======================================
Generates directly runnable Python test scripts using:
  - httpx + pytest for API tests
  - Playwright + pytest for UI tests

The generated scripts are self-contained: they include imports, fixtures,
test functions, and assertions. They can be run via subprocess with
``python -m pytest <script.py> --tb=short -q``.

This bypasses the lossy two-stage approach (generate documents → extract
params via LLM) and instead produces executable code in a single LLM call.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.llm_provider import LLMResponse, get_llm_provider
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GeneratedScript:
    """A single generated test script."""
    filename: str
    code: str
    test_functions: List[str] = field(default_factory=list)
    execution_type: str = "api"  # "api" or "ui"
    description: str = ""


@dataclass
class ExecutableGenerateResult:
    """Result from executable generation."""
    scripts: List[GeneratedScript] = field(default_factory=list)
    summary: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    provider: str = ""


# ---------------------------------------------------------------------------
# Reference scripts (few-shot examples for the LLM)
# ---------------------------------------------------------------------------

_API_REFERENCE_SCRIPT = '''\
"""Auto-generated API tests for {app_name}."""
import os
import httpx
import pytest

BASE_URL = os.environ.get("QAFORGE_BASE_URL", "")
SSL_VERIFY = os.environ.get("QAFORGE_SSL_VERIFY", "false").lower() == "true"


def test_health_check():
    """Verify the API is reachable."""
    resp = httpx.get(f"{{BASE_URL}}/", timeout=10, verify=SSL_VERIFY)
    assert resp.status_code in (200, 307, 404), f"API unreachable: {{resp.status_code}}"


def test_list_endpoint(auth_headers):
    """Verify a list endpoint returns 200 with array data."""
    resp = httpx.get(
        f"{{BASE_URL}}{example_list_endpoint}",
        headers=auth_headers, timeout=30, verify=SSL_VERIFY,
    )
    assert resp.status_code == 200, f"Expected 200, got {{resp.status_code}}: {{resp.text[:200]}}"
    data = resp.json()
    assert isinstance(data, (list, dict)), f"Expected list or dict, got {{type(data).__name__}}"
'''

_UI_REFERENCE_SCRIPT = '''\
"""Auto-generated Playwright UI tests for {app_name}."""
import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("QAFORGE_BASE_URL", "") or os.environ.get("QAFORGE_APP_URL", "")
AUTH_EMAIL = os.environ.get("QAFORGE_AUTH_EMAIL", "")
AUTH_PASSWORD = os.environ.get("QAFORGE_AUTH_PASSWORD", "")


@pytest.fixture(scope="module")
def browser_context(browser):
    """Create a browser context with reasonable defaults."""
    context = browser.new_context(
        viewport={{"width": 1280, "height": 720}},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture
def logged_in_page(browser_context):
    """Navigate to app and log in using credentials from environment."""
    page = browser_context.new_page()
    page.goto(f"{{BASE_URL}}{login_route}")
    page.wait_for_load_state("networkidle")
    page.get_by_label("Email").fill(AUTH_EMAIL)
    page.get_by_label("Password").fill(AUTH_PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url("**/dashboard**", timeout=15000)
    yield page
    page.close()


def test_login_page_loads():
    """Verify login page is accessible."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{{BASE_URL}}{login_route}")
        expect(page.get_by_role("button", name="Login")).to_be_visible()
        browser.close()
'''


# ---------------------------------------------------------------------------
# Executable Generator
# ---------------------------------------------------------------------------

class ExecutableGenerator:
    """
    Generates executable Python test scripts from app profile + requirements.

    Usage::

        gen = ExecutableGenerator()
        result = gen.generate_api_tests(
            app_profile=project.app_profile,
            description="Test candidate CRUD and auth",
            requirements=["REQ-001: User login", "REQ-002: CRUD candidates"],
        )
        for script in result.scripts:
            print(script.filename)
            print(script.code)
    """

    def generate_api_tests(
        self,
        app_profile: Dict[str, Any],
        description: str,
        requirements: Optional[List[str]] = None,
        count: int = 10,
        additional_context: str = "",
    ) -> ExecutableGenerateResult:
        """Generate executable API test scripts using httpx + pytest."""

        provider = get_llm_provider()
        system_prompt = self._build_api_system_prompt()
        user_prompt = self._build_api_user_prompt(
            app_profile, description, requirements, count, additional_context,
        )

        def _call():
            return provider.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=16384,
                temperature=0.3,
                model=provider.smart_model,
            )

        response: LLMResponse = retry_with_backoff(_call, max_retries=2, base_delay=1.5)
        code = self._extract_python_code(response.text)

        if not code:
            logger.error("LLM did not return valid Python code for API tests")
            return ExecutableGenerateResult(
                summary="Failed to generate executable tests — LLM returned no valid Python",
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
            )

        # Sanitize: remove any hardcoded credentials the LLM may have embedded
        code = self._sanitize_generated_code(code, app_profile)

        # Extract test function names
        test_funcs = re.findall(r"^def (test_\w+)", code, re.MULTILINE)

        script = GeneratedScript(
            filename="test_api_generated.py",
            code=code,
            test_functions=test_funcs,
            execution_type="api",
            description=description[:200],
        )

        logger.info(
            "Generated executable API test: %d functions, %d chars | %s/%s %d+%d tokens",
            len(test_funcs), len(code), response.provider, response.model,
            response.tokens_in, response.tokens_out,
        )

        return ExecutableGenerateResult(
            scripts=[script],
            summary=f"Generated {len(test_funcs)} API test functions",
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            model=response.model or "",
            provider=response.provider or "",
        )

    def generate_ui_tests(
        self,
        app_profile: Dict[str, Any],
        description: str,
        requirements: Optional[List[str]] = None,
        count: int = 8,
        additional_context: str = "",
    ) -> ExecutableGenerateResult:
        """Generate executable Playwright UI test scripts."""

        provider = get_llm_provider()
        system_prompt = self._build_ui_system_prompt()
        user_prompt = self._build_ui_user_prompt(
            app_profile, description, requirements, count, additional_context,
        )

        def _call():
            return provider.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=16384,
                temperature=0.3,
                model=provider.smart_model,
            )

        response: LLMResponse = retry_with_backoff(_call, max_retries=2, base_delay=1.5)
        code = self._extract_python_code(response.text)

        if not code:
            logger.error("LLM did not return valid Python code for UI tests")
            return ExecutableGenerateResult(
                summary="Failed to generate executable tests — LLM returned no valid Python",
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
            )

        # Sanitize: remove any hardcoded credentials the LLM may have embedded
        code = self._sanitize_generated_code(code, app_profile)

        test_funcs = re.findall(r"^def (test_\w+)", code, re.MULTILINE)

        script = GeneratedScript(
            filename="test_ui_generated.py",
            code=code,
            test_functions=test_funcs,
            execution_type="ui",
            description=description[:200],
        )

        logger.info(
            "Generated executable UI test: %d functions, %d chars | %s/%s %d+%d tokens",
            len(test_funcs), len(code), response.provider, response.model,
            response.tokens_in, response.tokens_out,
        )

        return ExecutableGenerateResult(
            scripts=[script],
            summary=f"Generated {len(test_funcs)} UI test functions",
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            model=response.model or "",
            provider=response.provider or "",
        )

    # ------------------------------------------------------------------
    # System prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _build_api_system_prompt() -> str:
        return """You are QAForge, an expert test automation engineer.
Your task: generate a COMPLETE, RUNNABLE Python test module using httpx and pytest.

RULES:
1. Output ONLY the Python code — no explanation, no markdown outside the code block.
2. Wrap the entire output in ```python ... ``` fences.
3. The script must be self-contained: all imports at the top.
4. Use httpx (NOT requests) for HTTP calls. Use pytest assertions.
5. Read BASE_URL from environment: `BASE_URL = os.environ.get("QAFORGE_BASE_URL", "")`. Import os at top.
6. Do NOT define auth_token or auth_headers fixtures — they are provided by conftest.py.
   Available fixtures from conftest:
   - `client` — httpx.Client with base_url + SSL disabled (NO auth headers)
   - `authenticated_client` — httpx.Client with base_url + auth headers + SSL disabled
   - `auth_token` — JWT token string (may be empty if no auth configured)
   - `auth_headers` — dict with Authorization header (may be empty)
   - `base_url`, `app_url` — URL strings from environment
   Use `client` for unauthenticated tests (login, health check).
   Use `authenticated_client` or pass `auth_headers` for protected endpoints.
7. Use `verify=False` on ALL httpx calls (for self-signed certs). Or use the `client` fixture.
8. Each test function must:
   - Have a clear docstring explaining what it tests
   - Use real endpoints from the app profile (NEVER invent endpoints)
   - Assert specific status codes, response fields, and data types
   - Handle both success and error scenarios
   - Be independent (no dependency on other test execution order)
9. NEVER hardcode passwords, tokens, or secrets as string literals.
   Read credentials from env: `os.environ.get("QAFORGE_AUTH_EMAIL", "")`.
10. Include cleanup: if a test creates a resource, delete it in a finally block.
11. Use realistic but safe test data (test_user@example.com, "Test User", etc.)
12. Set timeout=30 on all httpx calls, or use the `client` fixture.
13. Name test functions descriptively: test_create_user, test_list_users_pagination, etc."""

    @staticmethod
    def _build_ui_system_prompt() -> str:
        return """You are QAForge, an expert test automation engineer.
Your task: generate a COMPLETE, RUNNABLE Python test module using Playwright and pytest.

RULES:
1. Output ONLY the Python code — no explanation, no markdown outside the code block.
2. Wrap the entire output in ```python ... ``` fences.
3. The script must be self-contained: all imports at the top.
4. Use playwright.sync_api (sync, NOT async). Use pytest assertions and Playwright expect().
5. Read BASE_URL from environment: `BASE_URL = os.environ.get("QAFORGE_APP_URL", "") or os.environ.get("QAFORGE_BASE_URL", "")`. Import os at top.
6. Read credentials from environment: `os.environ.get("QAFORGE_AUTH_EMAIL", "")` and `os.environ.get("QAFORGE_AUTH_PASSWORD", "")`.
   NEVER hardcode passwords, tokens, or secrets as string literals.
7. Always use `ignore_https_errors=True` when creating browser contexts (for self-signed certs).
8. PREFER semantic locators:
   - page.get_by_role("button", name="Submit")
   - page.get_by_label("Email")
   - page.get_by_text("Dashboard")
   - page.get_by_placeholder("Search...")
9. AVOID fragile CSS selectors unless no semantic alternative exists.
10. Use proper wait strategies:
    - page.wait_for_load_state("networkidle")
    - page.wait_for_url("**/dashboard**")
    - expect(locator).to_be_visible(timeout=10000)
11. Take screenshot on failure: page.screenshot(path="failure_<test_name>.png")
12. Each test function must have a clear docstring.
13. Handle SPA navigation: wait for URL changes or specific elements, not hard sleeps."""

    # ------------------------------------------------------------------
    # User prompts
    # ------------------------------------------------------------------

    def _build_api_user_prompt(
        self,
        app_profile: Dict[str, Any],
        description: str,
        requirements: Optional[List[str]],
        count: int,
        additional_context: str,
    ) -> str:
        parts: List[str] = [
            f"Generate a Python test module with approximately {count} test functions "
            f"for the following system.\n",
            f"=== WHAT TO TEST ===\n{description[:4000]}\n",
        ]

        # App profile
        ap_text = self._format_app_profile_for_prompt(app_profile, mode="api")
        if ap_text:
            parts.append(
                f"=== APPLICATION PROFILE (use EXACT endpoints from this list) ===\n"
                f"CRITICAL: Use ONLY these endpoints. Do NOT invent or guess paths.\n\n"
                f"{ap_text}\n"
            )

        if requirements:
            parts.append(
                "=== REQUIREMENTS ===\n"
                + "\n".join(f"- {r}" for r in requirements[:20])
                + "\n"
            )

        if additional_context:
            parts.append(f"=== ADDITIONAL CONTEXT ===\n{additional_context[:2000]}\n")

        parts.append(
            "Generate the complete Python test module now. "
            "Remember: use httpx, pytest, real endpoints from the profile above."
        )

        return "\n".join(parts)

    def _build_ui_user_prompt(
        self,
        app_profile: Dict[str, Any],
        description: str,
        requirements: Optional[List[str]],
        count: int,
        additional_context: str,
    ) -> str:
        parts: List[str] = [
            f"Generate a Python Playwright test module with approximately {count} test functions "
            f"for the following web application.\n",
            f"=== WHAT TO TEST ===\n{description[:4000]}\n",
        ]

        ap_text = self._format_app_profile_for_prompt(app_profile, mode="ui")
        if ap_text:
            parts.append(
                f"=== APPLICATION PROFILE ===\n"
                f"Use ONLY pages and elements listed here. Do NOT guess selectors.\n\n"
                f"{ap_text}\n"
            )

        if requirements:
            parts.append(
                "=== REQUIREMENTS ===\n"
                + "\n".join(f"- {r}" for r in requirements[:20])
                + "\n"
            )

        if additional_context:
            parts.append(f"=== ADDITIONAL CONTEXT ===\n{additional_context[:2000]}\n")

        parts.append(
            "Generate the complete Python Playwright test module now. "
            "Remember: use playwright.sync_api, pytest, semantic locators."
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_app_profile_for_prompt(
        app_profile: Dict[str, Any], mode: str = "api"
    ) -> str:
        """Format app profile as structured text for the LLM prompt."""
        if not app_profile:
            return ""

        lines: List[str] = []

        if app_profile.get("app_url"):
            lines.append(f"App URL: {app_profile['app_url']}")
        if app_profile.get("api_base_url"):
            lines.append(f"API Base URL: {app_profile['api_base_url']}")

        # Tech stack
        ts = app_profile.get("tech_stack", {})
        if isinstance(ts, dict) and any(ts.values()):
            lines.append(f"Tech Stack: {', '.join(f'{k}: {v}' for k, v in ts.items() if v)}")

        # Auth — scrub actual credentials, reference env vars instead
        auth = app_profile.get("auth", {})
        if isinstance(auth, dict) and auth.get("login_endpoint"):
            lines.append(f"\nAuthentication:")
            lines.append(f"  Login endpoint: POST {auth['login_endpoint']}")
            if auth.get("request_body"):
                # Show request body structure but replace actual values
                body = auth["request_body"]
                if isinstance(body, dict):
                    scrubbed = {k: "<from env>" for k in body}
                    lines.append(f"  Request body format: {scrubbed}")
                else:
                    lines.append(f"  Request body format: {body}")
            if auth.get("token_header"):
                lines.append(f"  Token header: {auth['token_header']}")
            lines.append(f"  Test credentials: available via os.environ (QAFORGE_AUTH_EMAIL, QAFORGE_AUTH_PASSWORD)")
            lines.append(f"  Auth token: available via auth_token / auth_headers fixtures from conftest.py")
            if auth.get("response_fields"):
                lines.append(f"  Login response fields: {', '.join(auth['response_fields'])}")

        # API Endpoints (for api mode)
        if mode == "api":
            endpoints = app_profile.get("api_endpoints", [])
            if isinstance(endpoints, list) and endpoints:
                lines.append(f"\nAPI Endpoints ({len(endpoints)} total):")
                for ep in endpoints[:40]:
                    if not isinstance(ep, dict):
                        continue
                    line = f"  {ep.get('method', 'GET')} {ep.get('path', '/')}"
                    if ep.get("description"):
                        line += f" — {ep['description']}"
                    if ep.get("required_fields") and isinstance(ep["required_fields"], list):
                        line += f"\n    Required fields: {', '.join(ep['required_fields'])}"
                    if ep.get("response_fields") and isinstance(ep["response_fields"], list):
                        line += f"\n    Response fields: {', '.join(ep['response_fields'])}"
                    if ep.get("test_data_hints") and isinstance(ep["test_data_hints"], dict):
                        line += f"\n    Example data: {json.dumps(ep['test_data_hints'])}"
                    lines.append(line)

        # UI Pages (for ui mode)
        if mode == "ui":
            pages = app_profile.get("ui_pages", [])
            if isinstance(pages, list) and pages:
                lines.append(f"\nUI Pages ({len(pages)} discovered):")
                for pg in pages[:20]:
                    if not isinstance(pg, dict):
                        continue
                    line = f"  Route: {pg.get('route', '/')}"
                    if pg.get("purpose"):
                        line += f" — {pg['purpose']}"
                    lines.append(line)
                    # Interactive elements
                    interactions = pg.get("interactions", [])
                    if isinstance(interactions, list):
                        for elem in interactions[:8]:
                            if isinstance(elem, dict):
                                locator = elem.get("locator", "")
                                purpose = elem.get("purpose", "")
                                lines.append(f"    - {elem.get('element', '?')}: {locator}")
                                if purpose:
                                    lines.append(f"      Purpose: {purpose}")
                    # Forms
                    forms = pg.get("forms", [])
                    if isinstance(forms, list):
                        for form in forms[:3]:
                            if isinstance(form, dict):
                                fields = form.get("fields", [])
                                lines.append(
                                    f"    Form: {form.get('name', 'unnamed')} "
                                    f"(fields: {', '.join(fields[:8])})"
                                )

        # RBAC
        if app_profile.get("rbac_model"):
            lines.append(f"\nRBAC: {app_profile['rbac_model']}")

        # Notes
        if app_profile.get("notes"):
            lines.append(f"\nNotes: {app_profile['notes']}")

        return "\n".join(lines)

    @staticmethod
    def _sanitize_generated_code(code: str, app_profile: dict) -> str:
        """Post-process generated code to replace any hardcoded credentials.

        Even with good prompts, LLMs sometimes embed actual passwords or URLs
        as string literals. This scrubs them out and replaces with env-var reads.
        """
        if not code or not app_profile:
            return code

        # Collect sensitive values to scrub
        sensitives: list[tuple[str, str]] = []

        # Password
        auth = app_profile.get("auth", {})
        if isinstance(auth, dict):
            creds = auth.get("test_credentials", {})
            if isinstance(creds, dict):
                pw = creds.get("password", "")
                if pw and len(pw) >= 4:
                    sensitives.append((pw, 'os.environ.get("QAFORGE_AUTH_PASSWORD", "")'))
                email = creds.get("email", "")
                if email and "@" in email:
                    sensitives.append((email, 'os.environ.get("QAFORGE_AUTH_EMAIL", "")'))

        # Base URL (replace hardcoded URL with env var)
        for url_key in ("api_base_url", "app_url"):
            url = app_profile.get(url_key, "")
            if url and len(url) > 10:
                sensitives.append((url, 'os.environ.get("QAFORGE_BASE_URL", "")'))

        # Apply replacements (longest first to avoid partial matches)
        sensitives.sort(key=lambda x: -len(x[0]))
        for literal, replacement in sensitives:
            if literal in code:
                # Replace as string assignment: `VAR = "literal"` → `VAR = os.environ.get(...)`
                code = code.replace(f'"{literal}"', replacement)
                code = code.replace(f"'{literal}'", replacement)
                logger.info("Sanitized hardcoded value (%d chars) from generated code", len(literal))

        # Ensure `import os` is present if we injected os.environ calls
        if 'os.environ' in code and '\nimport os' not in code and not code.startswith('import os'):
            code = "import os\n" + code

        return code

    @staticmethod
    def _extract_python_code(raw_response: str) -> str:
        """Extract Python code from LLM response (handles markdown fences)."""
        text = raw_response.strip()

        # Try to extract from ```python ... ``` fences
        match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try generic ``` ... ``` fences
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if "import" in code and "def test_" in code:
                return code

        # If no fences, check if the whole response looks like Python
        if text.startswith(("import ", "\"\"\"", "from ", "#")) and "def test_" in text:
            return text

        # Last resort: find the largest block that looks like Python code
        # (starts with import, contains def test_)
        lines = text.split("\n")
        code_lines: List[str] = []
        in_code = False
        for line in lines:
            if line.startswith(("import ", "from ", "\"\"\"", "#!", "BASE_URL", "def ", "class ", "@")):
                in_code = True
            if in_code:
                code_lines.append(line)

        code = "\n".join(code_lines).strip()
        if "def test_" in code:
            return code

        logger.warning("Could not extract Python code from LLM response (%d chars)", len(text))
        return ""
