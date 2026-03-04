"""QAForge MCP Server — Configuration"""
import os

QAFORGE_SERVER_NAME = os.getenv("QAFORGE_SERVER_NAME", "QAForge")
QAFORGE_API_URL = os.getenv("QAFORGE_API_URL", "http://backend:8000")
QAFORGE_AGENT_KEY = os.getenv("QAFORGE_AGENT_KEY", "")
