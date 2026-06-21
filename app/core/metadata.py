from app import __version__

APP_NAME = "QuoinAPI"
APP_DESCRIPTION = "The Foundation for your Python backend API"
REPOSITORY_URL = "https://github.com/balakmran/quoin-api"
COPYRIGHT_OWNER = "Balakumaran Manoharan"

APP_LONG_DESCRIPTION = """
QuoinAPI is a production-ready Python backend \
foundation built with FastAPI, SQLModel, and the Astral stack \
(uv, ruff, ty). It gives you a battle-tested starting point with \
type safety, observability, and clean architecture out of the box.
"""

VERSION = __version__

__all__ = [
    "APP_DESCRIPTION",
    "APP_LONG_DESCRIPTION",
    "APP_NAME",
    "COPYRIGHT_OWNER",
    "REPOSITORY_URL",
    "VERSION",
]
