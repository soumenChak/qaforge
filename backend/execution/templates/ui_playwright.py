"""
QAForge -- Playwright UI Test Template.

Executes browser-based UI tests using Playwright:
  1. Login (if credentials configured)
  2. Navigate to pages
  3. Interact with elements (click, fill, select)
  4. Assert visibility, text content, URLs
  5. Capture screenshots on failure

LLM-extracted params schema:
{
  "steps": [
    {"action": "navigate", "url": "/dashboard"},
    {"action": "click", "selector": "button.create-new"},
    {"action": "fill", "selector": "#name-input", "value": "Test Item"},
    {"action": "click", "selector": "button[type=submit]"},
    {"action": "wait", "ms": 1000},
    {"action": "assert_visible", "selector": ".success-toast"},
    {"action": "assert_text", "selector": "h1", "expected": "Dashboard"},
    {"action": "assert_url", "pattern": "/dashboard"},
    {"action": "screenshot", "name": "final-state"}
  ],
  "timeout_ms": 5000,
  "screenshot_on_failure": true
}
"""

import base64
import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a Playwright UI test.

    Args:
        params: LLM-extracted test parameters (steps, timeout, etc.)
        connection_config: Connection profile config (app_url, login_credentials, etc.)

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    app_url = connection_config.get("app_url") or connection_config.get("base_url", "")
    app_url = app_url.rstrip("/")
    login_config = connection_config.get("login_credentials") or {}
    viewport = connection_config.get("viewport", {"width": 1280, "height": 720})
    headless = connection_config.get("headless", True)
    default_timeout = params.get("timeout_ms", 5000)
    screenshot_on_failure = params.get("screenshot_on_failure", True)
    steps = params.get("steps") or []

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    screenshots: List[Dict[str, Any]] = []
    total_start = time.perf_counter()

    if not app_url:
        return {
            "passed": False,
            "assertions": [{"type": "connection", "expected": "app_url configured", "actual": "missing", "passed": False}],
            "logs": ["No app_url configured in connection"],
            "details": {},
        }

    if not steps:
        return {
            "passed": False,
            "assertions": [{"type": "steps_provided", "expected": "non-empty", "actual": "empty", "passed": False}],
            "logs": ["No test steps provided"],
            "details": {},
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "passed": False,
            "assertions": [{"type": "dependency", "expected": "playwright", "actual": "not installed", "passed": False}],
            "logs": ["Playwright is not installed. Add 'playwright' to requirements and run 'playwright install chromium'."],
            "details": {},
        }

    browser = None
    try:
        async with async_playwright() as p:
            logs.append(f"Launching browser (headless={headless})")
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport=viewport,
                ignore_https_errors=True,
            )
            page = await context.new_page()
            page.set_default_timeout(default_timeout)

            # Capture console messages for debugging
            console_logs: List[Dict[str, str]] = []
            page.on("console", lambda msg: console_logs.append({
                "level": msg.type, "text": msg.text[:200]
            }))

            # ── Login Flow (if configured) ──
            if login_config.get("username") and login_config.get("password"):
                login_url = login_config.get("login_url", "/login")
                full_login_url = f"{app_url}{login_url}" if login_url.startswith("/") else login_url
                logs.append(f"[Login] Navigating to {full_login_url}")

                await page.goto(full_login_url, wait_until="networkidle")

                username_sel = login_config.get("username_selector", "#email, #username, input[name=email], input[name=username]")
                password_sel = login_config.get("password_selector", "#password, input[name=password], input[type=password]")
                submit_sel = login_config.get("submit_selector", "button[type=submit], input[type=submit]")

                try:
                    await page.fill(username_sel, login_config["username"])
                    await page.fill(password_sel, login_config["password"])
                    await page.click(submit_sel)
                    await page.wait_for_load_state("networkidle")
                    logs.append("[Login] Login submitted successfully")
                    assertions.append({"type": "login", "expected": "success", "actual": "success", "passed": True})
                except Exception as e:
                    logs.append(f"[Login] FAILED: {e}")
                    assertions.append({"type": "login", "expected": "success", "actual": str(e)[:100], "passed": False})
                    passed = False
                    if screenshot_on_failure:
                        await _async_capture_screenshot(page, screenshots, "login_failure", logs)

            # ── Execute Test Steps ──
            for i, step in enumerate(steps):
                step_num = i + 1
                action = step.get("action", "").lower()
                step_start = time.perf_counter()

                try:
                    if action == "navigate":
                        url = step.get("url", "/")
                        full_url = f"{app_url}{url}" if url.startswith("/") else url
                        logs.append(f"[Step {step_num}] Navigate to {full_url}")
                        await page.goto(full_url, wait_until="networkidle")
                        step_ms = (time.perf_counter() - step_start) * 1000
                        logs.append(f"[Step {step_num}] Page loaded ({step_ms:.0f}ms) — {page.url}")

                    elif action == "click":
                        selector = step.get("selector", "")
                        logs.append(f"[Step {step_num}] Click {selector}")
                        await page.click(selector)
                        step_ms = (time.perf_counter() - step_start) * 1000
                        logs.append(f"[Step {step_num}] Clicked ({step_ms:.0f}ms)")

                    elif action == "fill":
                        selector = step.get("selector", "")
                        value = step.get("value", "")
                        logs.append(f"[Step {step_num}] Fill {selector} with '{value[:30]}...'")
                        await page.fill(selector, value)
                        step_ms = (time.perf_counter() - step_start) * 1000
                        logs.append(f"[Step {step_num}] Filled ({step_ms:.0f}ms)")

                    elif action == "select_option":
                        selector = step.get("selector", "")
                        value = step.get("value", "")
                        logs.append(f"[Step {step_num}] Select '{value}' in {selector}")
                        await page.select_option(selector, value)

                    elif action == "wait":
                        ms = step.get("ms", 1000)
                        logs.append(f"[Step {step_num}] Wait {ms}ms")
                        await page.wait_for_timeout(ms)

                    elif action == "wait_for_selector":
                        selector = step.get("selector", "")
                        logs.append(f"[Step {step_num}] Wait for {selector}")
                        await page.wait_for_selector(selector, state="visible")

                    elif action == "press_key":
                        key = step.get("key", "Enter")
                        selector = step.get("selector", "")
                        logs.append(f"[Step {step_num}] Press '{key}'" + (f" on {selector}" if selector else ""))
                        if selector:
                            await page.press(selector, key)
                        else:
                            await page.keyboard.press(key)

                    elif action == "hover":
                        selector = step.get("selector", "")
                        logs.append(f"[Step {step_num}] Hover {selector}")
                        await page.hover(selector)

                    elif action == "assert_visible":
                        selector = step.get("selector", "")
                        logs.append(f"[Step {step_num}] Assert visible: {selector}")
                        is_visible = await page.is_visible(selector)
                        assertions.append({
                            "type": "assert_visible",
                            "selector": selector,
                            "step": step_num,
                            "passed": is_visible,
                        })
                        if not is_visible:
                            passed = False
                            logs.append(f"[Step {step_num}] FAIL: Element '{selector}' not visible")
                            if screenshot_on_failure:
                                await _async_capture_screenshot(page, screenshots, f"step_{step_num}_assert_visible", logs)
                        else:
                            logs.append(f"[Step {step_num}] PASS: Element visible")

                    elif action == "assert_text":
                        selector = step.get("selector", "")
                        expected = step.get("expected", "")
                        logs.append(f"[Step {step_num}] Assert text of {selector} = '{expected[:30]}'")
                        actual = await page.text_content(selector)
                        text_ok = expected.lower() in (actual or "").lower()
                        assertions.append({
                            "type": "assert_text",
                            "selector": selector,
                            "expected": expected,
                            "actual": (actual or "")[:200],
                            "step": step_num,
                            "passed": text_ok,
                        })
                        if not text_ok:
                            passed = False
                            logs.append(f"[Step {step_num}] FAIL: Expected '{expected}', got '{(actual or '')[:50]}'")
                            if screenshot_on_failure:
                                await _async_capture_screenshot(page, screenshots, f"step_{step_num}_assert_text", logs)
                        else:
                            logs.append(f"[Step {step_num}] PASS: Text matches")

                    elif action == "assert_url":
                        pattern = step.get("pattern", "")
                        current_url = page.url
                        url_ok = pattern.lower() in current_url.lower()
                        assertions.append({
                            "type": "assert_url",
                            "expected_pattern": pattern,
                            "actual_url": current_url,
                            "step": step_num,
                            "passed": url_ok,
                        })
                        if not url_ok:
                            passed = False
                            logs.append(f"[Step {step_num}] FAIL: URL '{current_url}' does not contain '{pattern}'")
                        else:
                            logs.append(f"[Step {step_num}] PASS: URL contains '{pattern}'")

                    elif action == "assert_element_count":
                        selector = step.get("selector", "")
                        expected_count = step.get("expected_count", 0)
                        elements = await page.query_selector_all(selector)
                        actual_count = len(elements)
                        count_ok = actual_count == expected_count
                        assertions.append({
                            "type": "assert_element_count",
                            "selector": selector,
                            "expected": expected_count,
                            "actual": actual_count,
                            "step": step_num,
                            "passed": count_ok,
                        })
                        if not count_ok:
                            passed = False
                            logs.append(f"[Step {step_num}] FAIL: Expected {expected_count} elements, found {actual_count}")

                    elif action == "screenshot":
                        name = step.get("name", f"step_{step_num}")
                        await _async_capture_screenshot(page, screenshots, name, logs)
                        logs.append(f"[Step {step_num}] Screenshot captured: {name}")

                    else:
                        logs.append(f"[Step {step_num}] Unknown action: '{action}' — skipped")

                except Exception as exc:
                    passed = False
                    logs.append(f"[Step {step_num}] ERROR: {type(exc).__name__}: {exc}")
                    assertions.append({
                        "type": "step_execution",
                        "step": step_num,
                        "action": action,
                        "expected": "success",
                        "actual": str(exc)[:200],
                        "passed": False,
                    })
                    if screenshot_on_failure:
                        await _async_capture_screenshot(page, screenshots, f"step_{step_num}_error", logs)
                    # Continue to next step unless it's a navigation failure
                    if action == "navigate":
                        break

            # Close browser
            await browser.close()
            browser = None

    except Exception as exc:
        passed = False
        logs.append(f"Browser error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "browser_execution",
            "expected": "success",
            "actual": str(exc)[:200],
            "passed": False,
        })
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "ui_playwright",
            "total_duration_ms": round(total_ms, 1),
            "app_url": app_url,
            "steps_count": len(steps),
            "screenshots": screenshots,
            "console_logs": console_logs[:50] if 'console_logs' in dir() else [],
        },
    }


async def _async_capture_screenshot(page, screenshots, name, logs):
    """Capture a screenshot asynchronously."""
    try:
        raw = await page.screenshot(type="png", full_page=False)
        b64 = base64.b64encode(raw).decode("ascii")
        screenshots.append({
            "name": name,
            "base64": b64[:100000],  # Cap at ~75KB
        })
    except Exception as e:
        logs.append(f"  Screenshot capture failed: {e}")
