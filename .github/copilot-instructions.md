# Copilot Instructions

Follow these rules for all generated code:

- Use Python 3.12.
- Prefer async/await where possible.
- Use type hints everywhere.
- Follow PEP 8.
- For FastAPI:
  - Use dependency injection.
  - Use SQLAlchemy 2.0 async syntax.
  - Validate input with Pydantic.
- Write docstrings in English for public functions.
- Never use print(); use logging.
- Do NOT run `get_errors` tool unless explicitly asked to.