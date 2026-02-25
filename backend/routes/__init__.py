"""
QAForge -- Route modules package.

Each file in this directory should define an ``APIRouter`` named ``router``.
The main application will auto-discover and include them.

Modules:
    auth         - Authentication (login, register)
    users        - User management (CRUD, password change)
    projects     - Project CRUD with stats
    requirements - Requirements management + LLM extraction
    test_cases   - Test case CRUD, generation, rating, export
    templates    - Export template management
    settings     - LLM provider configuration
    feedback     - Quality metrics and corrections
    knowledge    - Knowledge base search and management
"""
