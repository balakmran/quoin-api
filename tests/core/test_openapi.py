import importlib

from fastapi import FastAPI

from app.core import config as config_module
from app.core import openapi as openapi_module
from app.core.config import Environment
from app.core.openapi import set_openapi_generator


def test_set_openapi_generator() -> None:
    """Test set_openapi_generator attaches the function."""
    app = FastAPI()
    set_openapi_generator(app)

    # The app.openapi attribute should be a bound method or partial
    # We can verify that calling app.openapi() returns a schema
    schema = app.openapi()
    assert schema is not None
    assert schema["openapi"] == "3.1.0"

    # Call it again to test caching (line 70 coverage)
    schema2 = app.openapi()
    assert schema2 is schema


def test_openapi_url_disabled_in_production() -> None:
    """B9 regression: /openapi.json is hidden in production like /docs.

    Reads/writes ``config_module.settings`` (not a name captured at
    import time) since other tests reload ``app.core.config`` and
    rebind its module-level ``settings`` to a fresh instance.
    """
    original_env = config_module.settings.ENV
    try:
        config_module.settings.ENV = Environment.production
        importlib.reload(openapi_module)
        assert openapi_module.OPENAPI_PARAMETERS["openapi_url"] is None
        assert openapi_module.OPENAPI_PARAMETERS["docs_url"] is None
        assert openapi_module.OPENAPI_PARAMETERS["redoc_url"] is None
    finally:
        config_module.settings.ENV = original_env
        importlib.reload(openapi_module)
