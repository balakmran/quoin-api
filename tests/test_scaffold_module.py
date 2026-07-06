from pathlib import Path

import pytest

from scripts.scaffold_module import (
    class_name,
    route_collection_name,
    scaffold_module,
    validate_module_name,
)


def _write_api(path: Path) -> None:
    """Write a representative ``app/api.py`` fixture."""
    path.parent.mkdir(parents=True)
    path.write_text(
        "from fastapi import APIRouter\n\n"
        "from app.modules.system import router as system_router\n"
        "from app.modules.user import router as user_router\n\n"
        "# Versioned API router\n"
        "v1_router = APIRouter()\n"
        "v1_router.include_router(user_router)\n\n"
        "# Top-level API router with version prefix\n"
        'api_router = APIRouter(prefix="/api/v1")\n'
        "api_router.include_router(v1_router)\n\n"
        "# System routes stay at root (health, ready, root page)\n"
        "system_router_root = system_router\n"
    )


def test_scaffold_module_creates_files_and_registers_router(
    tmp_path: Path,
) -> None:
    """A new module gets scaffolded and mounted in ``api.py``."""
    _write_api(tmp_path / "app" / "api.py")

    scaffold_module(root=tmp_path, module="order_item")

    module_dir = tmp_path / "app" / "modules" / "order_item"
    assert (module_dir / "__init__.py").read_text() == (
        "from app.modules.order_item.routes import router\n\n"
        '__all__ = ["router"]\n'
    )
    assert (module_dir / "routes.py").read_text() == (
        "from fastapi import APIRouter\n\n"
        'router = APIRouter(prefix="/order_items", tags=["order_items"])\n'
    )
    # Stubs are minimally working (not empty), with PascalCase classes.
    assert (
        "class OrderItemRepository:"
        in (module_dir / "repository.py").read_text()
    )
    assert "class OrderItemService:" in (module_dir / "service.py").read_text()
    assert (
        "class OrderItemBase(SQLModel):"
        in (module_dir / "schemas.py").read_text()
    )
    assert (
        "class OrderItemNotFoundError(NotFoundError):"
        in (module_dir / "exceptions.py").read_text()
    )
    # models.py stays a documented empty stub (a real table needs a
    # migration), so it has no class definition.
    models_text = (module_dir / "models.py").read_text()
    assert not any(
        line.startswith("class ") for line in models_text.splitlines()
    )
    assert models_text.startswith('"""')

    test_dir = tmp_path / "tests" / "modules" / "order_item"
    assert test_dir.is_dir()
    test_text = (test_dir / "test_routes.py").read_text()
    assert "def test_order_items_router_has_prefix() -> None:" in test_text
    assert 'assert router.prefix == "/order_items"' in test_text

    api_text = (tmp_path / "app" / "api.py").read_text()
    assert (
        "from app.modules.order_item import router as order_item_router"
        in api_text
    )
    assert "v1_router.include_router(order_item_router)" in api_text


def test_scaffold_module_refuses_existing_module(tmp_path: Path) -> None:
    """Existing modules are not overwritten."""
    _write_api(tmp_path / "app" / "api.py")
    (tmp_path / "app" / "modules" / "product").mkdir(parents=True)

    with pytest.raises(FileExistsError):
        scaffold_module(root=tmp_path, module="product")


@pytest.mark.parametrize(
    "module",
    ["Product", "order-item", "_private", "order__item"],
)
def test_validate_module_name_rejects_invalid_names(module: str) -> None:
    """Only snake_case package names are accepted."""
    with pytest.raises(ValueError):
        validate_module_name(module)


@pytest.mark.parametrize(
    ("module", "collection"),
    [
        ("product", "products"),
        ("company", "companies"),
        ("address", "addresses"),
        ("order_item", "order_items"),
    ],
)
def test_route_collection_name_pluralizes_last_segment(
    module: str,
    collection: str,
) -> None:
    """Route collection names use a simple plural form."""
    assert route_collection_name(module) == collection


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("product", "Product"),
        ("order_item", "OrderItem"),
        ("user", "User"),
    ],
)
def test_class_name_pascal_cases_module(module: str, expected: str) -> None:
    """Class prefixes are the PascalCase form of the module name."""
    assert class_name(module) == expected
