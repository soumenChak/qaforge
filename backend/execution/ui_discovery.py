"""
QAForge -- AI-Powered UI Page Discovery Agent
==============================================
Autonomous agent that explores web applications using Playwright,
captures screenshots + accessibility trees, and uses LLM (with vision)
to understand pages and extract semantic Playwright locators.

Works with ANY web app including SaaS platforms with dynamic CSS
(Reltio, Salesforce, ServiceNow, etc.) — no CSS selector dependency.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 15_000
MAX_ELEMENTS_PER_PAGE = 80
MAX_A11Y_TREE_CHARS = 12_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def discover_ui_pages(
    app_url: str,
    routes: List[str],
    auth_config: Optional[Dict[str, Any]] = None,
    crawl: bool = False,
    max_pages: int = 20,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> Dict[str, Any]:
    """
    Launch headless Playwright, login, visit pages, and use LLM + vision
    to discover interactive elements with semantic locators.

    Returns:
        {
            "pages": [ { route, purpose, interactions[], navigation[], ... } ],
            "stats": { pages_visited, elements_found, duration_seconds },
            "errors": [ { route, error } ],
        }
    """
    from playwright.async_api import async_playwright  # lazy import

    start = time.time()
    discovered: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    visited: Set[str] = set()
    queue = list(routes)
    total_elements = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)

        # ── Login ──
        if auth_config:
            login_ok = await _login(page, app_url, auth_config)
            if not login_ok:
                errors.append({"route": "/login", "error": "Login failed — discovery will continue without auth"})

        # ── Visit pages (BFS with optional crawl) ──
        while queue and len(visited) < max_pages:
            route = queue.pop(0)
            route = route.strip()
            if not route.startswith("/"):
                route = "/" + route
            if route in visited:
                continue
            visited.add(route)

            try:
                page_info = await _discover_single_page(page, app_url, route, timeout_ms)
                discovered.append(page_info)
                total_elements += len(page_info.get("interactions", []))

                # If crawl mode, add discovered navigation links to queue
                if crawl:
                    for link in page_info.get("navigation_links", []):
                        if link not in visited and link not in queue:
                            queue.append(link)
            except Exception as exc:
                logger.warning("Discovery failed for %s: %s", route, exc)
                errors.append({"route": route, "error": str(exc)[:200]})

        await browser.close()

    duration = round(time.time() - start, 2)
    return {
        "pages": discovered,
        "stats": {
            "pages_visited": len(visited),
            "pages_discovered": len(discovered),
            "elements_found": total_elements,
            "duration_seconds": duration,
        },
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

async def _login(page, app_url: str, auth_config: Dict[str, Any]) -> bool:
    """Login via browser using auth config. Returns True on success."""
    email = auth_config.get("email", "")
    password = auth_config.get("password", "")
    if not email or not password:
        return False

    login_route = auth_config.get("login_url", "/login")
    full_url = f"{app_url.rstrip('/')}{login_route}"

    try:
        await page.goto(full_url, wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Use semantic locators for login — works on any app
        selectors = auth_config.get("selectors", {})

        # Username/email field
        username_sel = selectors.get("username_selector")
        if username_sel:
            await page.fill(username_sel, email)
        else:
            # Try semantic locators in order
            filled = False
            for locator_fn in [
                lambda: page.get_by_label("Email"),
                lambda: page.get_by_label("Username"),
                lambda: page.get_by_placeholder(re.compile(r"email|username|login", re.I)),
                lambda: page.locator("input[type='email'], input[name='email'], input[name='username'], #email, #username"),
            ]:
                try:
                    loc = locator_fn()
                    if await loc.count() > 0:
                        await loc.first.fill(email)
                        filled = True
                        break
                except Exception:
                    continue
            if not filled:
                logger.warning("Could not find username/email field for login")
                return False

        # Password field
        password_sel = selectors.get("password_selector")
        if password_sel:
            await page.fill(password_sel, password)
        else:
            try:
                loc = page.get_by_label(re.compile(r"password", re.I))
                if await loc.count() > 0:
                    await loc.first.fill(password)
                else:
                    await page.locator("input[type='password']").first.fill(password)
            except Exception:
                logger.warning("Could not find password field for login")
                return False

        # Submit
        submit_sel = selectors.get("submit_selector")
        if submit_sel:
            await page.click(submit_sel)
        else:
            try:
                loc = page.get_by_role("button", name=re.compile(r"log.?in|sign.?in|submit", re.I))
                if await loc.count() > 0:
                    await loc.first.click()
                else:
                    await page.locator("button[type='submit'], input[type='submit']").first.click()
            except Exception:
                logger.warning("Could not find submit button for login")
                return False

        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Check if we left the login page
        if "/login" not in page.url.lower():
            logger.info("Login successful — redirected to %s", page.url)
            return True
        else:
            logger.warning("Login may have failed — still on login page: %s", page.url)
            return False

    except Exception as exc:
        logger.error("Login failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Single page discovery
# ---------------------------------------------------------------------------

async def _discover_single_page(
    page, app_url: str, route: str, timeout_ms: int,
) -> Dict[str, Any]:
    """Navigate to a page, capture screenshot + a11y tree, analyze with LLM."""

    full_url = f"{app_url.rstrip('/')}{route}"
    logger.info("Discovering page: %s", full_url)

    await page.goto(full_url, wait_until="networkidle")
    await page.wait_for_timeout(1500)  # Extra settle time for SPAs

    # 1. Capture screenshot
    screenshot_bytes = await page.screenshot(type="png", full_page=False)
    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")

    # 2. Get accessibility tree
    a11y_tree = await page.accessibility.snapshot()
    a11y_json = json.dumps(a11y_tree, indent=1, default=str)[:MAX_A11Y_TREE_CHARS]

    # 3. Get page title + URL
    page_title = await page.title()
    current_url = page.url

    # 4. Send to LLM for analysis
    page_info = await _analyze_page_with_llm(
        screenshot_b64=screenshot_b64,
        a11y_tree_json=a11y_json,
        route=route,
        page_title=page_title,
        current_url=current_url,
    )

    return page_info


# ---------------------------------------------------------------------------
# LLM analysis (vision + accessibility tree)
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM_PROMPT = """You are an expert QA automation engineer analyzing a web application page.
You will receive a screenshot and an accessibility tree of the page.
Your job is to identify ALL interactive elements and provide Playwright SEMANTIC locators.

CRITICAL RULES:
- Use ONLY Playwright semantic locators (NOT CSS selectors):
  * page.get_by_role("button", name="Submit")
  * page.get_by_label("Email")
  * page.get_by_placeholder("Search...")
  * page.get_by_text("Create New")
  * page.get_by_role("link", name="Dashboard")
  * page.get_by_role("textbox", name="Name")
  * page.get_by_role("combobox", name="Status")
  * page.get_by_role("table")
  * page.get_by_role("heading", name="Entity Management")
- CSS selectors are FRAGILE (dynamic classes change across builds). Avoid them.
- Include EVERY interactive element you can see (inputs, buttons, links, dropdowns, tables, tabs, menus)
- For navigation, describe how to reach this page from common starting points
- Identify ALL visible links/nav items that lead to other pages

Return ONLY valid JSON (no markdown, no explanation)."""

_ANALYSIS_USER_PROMPT = """Analyze this web application page.

Route: {route}
Page title: {page_title}
Current URL: {current_url}

Accessibility tree (truncated):
{a11y_tree}

Identify all interactive elements and return this JSON structure:
{{
  "route": "{route}",
  "purpose": "One-line description of what this page is for",
  "interactions": [
    {{
      "element": "Human-readable element name",
      "locator": "Playwright semantic locator code (e.g. page.get_by_role('button', name='Submit'))",
      "purpose": "What this element does",
      "category": "input|button|link|dropdown|table|tab|menu|other"
    }}
  ],
  "navigation": [
    "How to reach this page (e.g. 'Click Entities in the sidebar')"
  ],
  "navigation_links": [
    "/path1", "/path2"
  ],
  "forms": [
    {{
      "name": "Form name or purpose",
      "fields": ["Field 1 label", "Field 2 label"]
    }}
  ],
  "tables": [
    {{
      "name": "Table name or purpose",
      "columns": ["Column 1", "Column 2"]
    }}
  ]
}}"""


async def _analyze_page_with_llm(
    screenshot_b64: str,
    a11y_tree_json: str,
    route: str,
    page_title: str,
    current_url: str,
) -> Dict[str, Any]:
    """Send screenshot + accessibility tree to LLM for page analysis."""
    from core.llm_provider import get_llm_provider

    provider = get_llm_provider()

    user_prompt = _ANALYSIS_USER_PROMPT.format(
        route=route,
        page_title=page_title,
        current_url=current_url,
        a11y_tree=a11y_tree_json,
    )

    # Build message with image (vision) — Anthropic format
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64[:200_000],  # cap at ~150KB
                    },
                },
                {
                    "type": "text",
                    "text": user_prompt,
                },
            ],
        }
    ]

    try:
        resp = provider.complete(
            system=_ANALYSIS_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=4096,
            temperature=0.2,
            model=provider.smart_model,  # Use smart model for vision analysis
        )

        # Parse JSON from response
        text = resp.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        page_info = json.loads(text)

        # Ensure route is set
        page_info.setdefault("route", route)

        logger.info(
            "Discovered page %s: %d interactions, %d nav links (tokens: %d/%d)",
            route,
            len(page_info.get("interactions", [])),
            len(page_info.get("navigation_links", [])),
            resp.tokens_in,
            resp.tokens_out,
        )
        return page_info

    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON for %s: %s", route, exc)
        return {
            "route": route,
            "purpose": f"Page at {route} (analysis failed — invalid JSON)",
            "interactions": [],
            "navigation": [],
            "navigation_links": [],
            "error": f"JSON parse error: {str(exc)[:100]}",
        }
    except Exception as exc:
        logger.error("LLM analysis failed for %s: %s", route, exc)
        return {
            "route": route,
            "purpose": f"Page at {route} (analysis failed)",
            "interactions": [],
            "navigation": [],
            "navigation_links": [],
            "error": str(exc)[:200],
        }
