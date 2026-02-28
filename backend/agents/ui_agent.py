"""
QAForge -- UI Testing Agent
==============================
Specialised QA agent for browser-based UI testing using Playwright.

Covers:
  - Login / authentication flows
  - Form submission & validation
  - Navigation & routing
  - CRUD operations through the UI
  - Responsive layout checks
  - Accessibility basics
  - Error states & edge cases
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.base_qa_agent import BaseQAAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain knowledge
# ---------------------------------------------------------------------------

_UI_COMMON_PATTERNS = """\
=== UI / BROWSER TESTING DOMAIN KNOWLEDGE ===

You are generating test cases for browser-based UI testing using Playwright.
Apply the following domain expertise when constructing tests:

1. LOGIN & AUTHENTICATION FLOWS
   - Valid login: fill email + password → submit → verify redirect to dashboard
   - Invalid credentials: wrong password → verify error message visible
   - Empty fields: submit without filling → verify validation messages
   - Session persistence: login → refresh page → verify still logged in
   - Logout: click logout → verify redirect to login page
   - Protected routes: navigate to /dashboard without login → verify redirect to /login

2. FORM SUBMISSION & VALIDATION
   - Happy path: fill all required fields → submit → verify success toast/redirect
   - Missing required fields: leave field empty → verify inline validation error
   - Invalid format: enter "not-an-email" in email field → verify format error
   - Max length: enter extremely long text → verify truncation or error
   - Select/dropdown: choose option → verify selection persists
   - Date picker: select date → verify format in field
   - File upload: attach file → verify preview/success indicator

3. NAVIGATION & ROUTING
   - Sidebar/navbar links: click each link → verify page loads with correct heading
   - Breadcrumbs: verify breadcrumb trail updates on navigation
   - Back button: navigate forward → click back → verify previous page state
   - Deep linking: navigate directly to /items/123 → verify item detail loads
   - 404 handling: navigate to /nonexistent → verify 404 page shown

4. CRUD OPERATIONS THROUGH UI
   - Create: click "Add" button → fill form → submit → verify new item in list
   - Read: click item in list → verify detail page shows correct data
   - Update: click edit → change field → save → verify change persists
   - Delete: click delete → confirm dialog → verify item removed from list
   - List operations: verify search, filter, sort, pagination work

5. RESPONSIVE & VISUAL
   - Desktop viewport (1280px): verify layout is correct
   - Tablet viewport (768px): verify responsive adjustments
   - Mobile viewport (375px): verify mobile menu, stacked layout
   - Modal/dialog: verify opens centered, closes on X or outside click
   - Loading states: verify spinners/skeletons appear during data fetch

6. ERROR STATES
   - Network error: offline/API down → verify user-friendly error message
   - Empty state: no data → verify "No items found" message (not blank page)
   - Permission denied: restricted action → verify appropriate message

7. PLAYWRIGHT-SPECIFIC GUIDANCE
   - PREFER semantic locators: get_by_role(), get_by_label(), get_by_text(), get_by_placeholder()
   - AVOID brittle CSS selectors unless no semantic alternative exists
   - Use networkidle or specific element visibility waits (not hard sleep)
   - Take screenshots on assertion failures
   - Handle SPA navigation: wait for URL change or specific content to appear
"""

_REACT_PATTERNS = """\
=== REACT SPA-SPECIFIC PATTERNS ===
- Client-side routing: URL changes without full page reload
- React state: verify UI updates after state changes (no stale data)
- Controlled forms: input values driven by state, onChange handlers
- Lazy loading: components may render after initial page load
- Toast notifications: appear briefly, may need to wait for visibility
- Material-UI / Ant Design: components use role attributes (dialog, button, tab)
- Error boundaries: verify app doesn't crash on component errors
"""


class UIAgent(BaseQAAgent):
    """
    UI Testing Agent -- generates test cases for browser-based UI testing
    using Playwright with deep knowledge of web application patterns.
    """

    SUB_DOMAIN_REACT = "react"
    SUB_DOMAIN_GENERIC = "generic"

    DEFAULT_MAX_TOKENS: int = 8192

    def __init__(
        self,
        sub_domain: str = SUB_DOMAIN_GENERIC,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.sub_domain = sub_domain.lower().strip()
        logger.info("UIAgent initialised. sub_domain=%s", self.sub_domain)

    def get_domain_patterns(self) -> str:
        """Return UI testing domain knowledge for prompt injection."""
        patterns = _UI_COMMON_PATTERNS

        if self.sub_domain == self.SUB_DOMAIN_REACT:
            patterns += "\n" + _REACT_PATTERNS
        else:
            patterns += (
                "\n=== GENERIC WEB APP ===\n"
                "Apply general web UI testing patterns. Use semantic locators "
                "(get_by_role, get_by_label, get_by_text) wherever possible."
            )

        return patterns

    def generate_test_cases(
        self,
        description: str,
        context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate UI-focused test cases for Playwright execution.

        Args:
            description: The UI requirement / feature description.
            context: Additional context (app profile with ui_pages, KB).
            config: Optional overrides (count, temperature, etc.).

        Returns:
            List of test-case dicts with execution_type="ui".
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

        # Tag with UI domain
        for tc in test_cases:
            tags = tc.get("domain_tags", [])
            if "ui" not in [t.lower() for t in tags]:
                tags.append("UI")
            if "playwright" not in [t.lower() for t in tags]:
                tags.append("Playwright")
            tc["domain_tags"] = tags
            if not tc.get("execution_type"):
                tc["execution_type"] = "ui"

        logger.info(
            "UIAgent generated %d test cases (requested %d) | tokens_in=%d tokens_out=%d",
            len(test_cases), count, response.tokens_in, response.tokens_out,
        )
        return test_cases
