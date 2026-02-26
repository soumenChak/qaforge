"""
QAForge -- Sandboxed Script Execution (LLM Fallback).

When no pre-built template matches, the LLM generates a Python test script.
This module executes it in a subprocess with:
  - Timeout (default 30s)
  - Restricted environment
  - Captured stdout/stderr

The script is expected to print a JSON result to stdout:
{
  "passed": true/false,
  "assertions": [...],
  "logs": [...]
}
"""

import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds


async def execute_script(
    script: str,
    timeout: int = DEFAULT_TIMEOUT,
    env_vars: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Execute a Python test script in a subprocess sandbox.

    Args:
        script: Python source code to execute.
        timeout: Maximum execution time in seconds.
        env_vars: Optional environment variables to pass to subprocess.

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    assertions = []
    logs = []
    passed = False

    # Write script to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="qaforge_test_",
        delete=False,
    ) as f:
        f.write(script)
        script_path = f.name

    try:
        # Build safe environment
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": tempfile.gettempdir(),
            "PYTHONPATH": "",
            "LANG": "en_US.UTF-8",
        }
        if env_vars:
            safe_env.update(env_vars)

        logs.append(f"Executing sandboxed script (timeout={timeout}s)")

        proc = await asyncio.create_subprocess_exec(
            "python3", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
            cwd=tempfile.gettempdir(),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            logs.append(f"Script timed out after {timeout}s")
            assertions.append({
                "type": "execution",
                "expected": "completed",
                "actual": "timeout",
                "passed": False,
            })
            return {
                "passed": False,
                "assertions": assertions,
                "logs": logs,
                "details": {"exit_code": -1, "error": "timeout"},
            }

        exit_code = proc.returncode
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if stderr_text:
            logs.append(f"stderr: {stderr_text[:500]}")

        if exit_code != 0:
            logs.append(f"Script exited with code {exit_code}")
            assertions.append({
                "type": "execution",
                "expected": "exit_code_0",
                "actual": f"exit_code_{exit_code}",
                "passed": False,
            })
            return {
                "passed": False,
                "assertions": assertions,
                "logs": logs,
                "details": {
                    "exit_code": exit_code,
                    "stdout": stdout_text[:500],
                    "stderr": stderr_text[:500],
                },
            }

        # Try to parse JSON output
        try:
            result = json.loads(stdout_text)
            passed = result.get("passed", False)
            assertions = result.get("assertions", [])
            script_logs = result.get("logs", [])
            logs.extend(script_logs)
            logs.append(f"Script completed: {'PASSED' if passed else 'FAILED'}")
        except json.JSONDecodeError:
            # Script didn't produce valid JSON -- treat stdout as logs
            logs.append("Script output (not JSON):")
            logs.append(stdout_text[:500])
            # If exit code 0, consider it passed
            passed = exit_code == 0
            assertions.append({
                "type": "script_output",
                "expected": "json_result",
                "actual": "plain_text",
                "passed": passed,
            })

    except Exception as exc:
        logs.append(f"Sandbox error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "execution",
            "expected": "success",
            "actual": str(exc),
            "passed": False,
        })
    finally:
        # Clean up temp file
        try:
            os.unlink(script_path)
        except OSError:
            pass

    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {"sandbox": True},
    }
