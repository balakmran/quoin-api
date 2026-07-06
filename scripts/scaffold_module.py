"""Scaffold a QuoinAPI feature module."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def class_name(module: str) -> str:
    """Return the PascalCase class prefix for a module.

    Args:
        module: Valid snake_case module name.

    Returns:
        The PascalCase form, e.g. ``order_item`` -> ``OrderItem``.
    """
    module = validate_module_name(module)
    return "".join(part.capitalize() for part in module.split("_"))


def _models_stub(module: str) -> str:
    """Return the ``models.py`` stub for a module."""
    return (
        f'"""Database models for the {module} module.\n\n'
        "Define a SQLModel table class here (mirror\n"
        "app/modules/user/models.py), then generate a migration with\n"
        "``just migrate-gen``. Left empty by the scaffold because a real\n"
        'table requires a migration.\n"""\n'
    )


def _schemas_stub(module: str) -> str:
    """Return the ``schemas.py`` stub for a module."""
    cls = class_name(module)
    return (
        f'"""Request/response schemas for the {module} module."""\n\n'
        "from sqlmodel import SQLModel\n\n\n"
        f"class {cls}Base(SQLModel):\n"
        f'    """Shared fields for {cls} request/response schemas."""\n'
    )


def _exceptions_stub(module: str) -> str:
    """Return the ``exceptions.py`` stub for a module."""
    cls = class_name(module)
    return (
        f'"""Domain exceptions for the {module} module."""\n\n'
        "from app.core.exceptions import NotFoundError\n\n\n"
        f"class {cls}NotFoundError(NotFoundError):\n"
        f'    """Raised when a {module} is not found."""\n\n'
        f"    def __init__(self, {module}_id: str) -> None:\n"
        f'        """Initialize {cls}NotFoundError."""\n'
        "        super().__init__(\n"
        # Split into two implicitly-concatenated pieces so the line
        # stays under the 80-char limit for long module names; ruff
        # format collapses it back for short ones.
        "            message=(\n"
        f'                f"{cls} with ID "\n'
        f"                f\"'{{{module}_id}}' not found\"\n"
        "            )\n"
        "        )\n"
    )


def _repository_stub(module: str) -> str:
    """Return the ``repository.py`` stub for a module."""
    cls = class_name(module)
    return (
        f'"""Data-access layer for the {module} module."""\n\n'
        "from sqlmodel.ext.asyncio.session import AsyncSession\n\n\n"
        f"class {cls}Repository:\n"
        f'    """Async CRUD for {cls} records.\n\n'
        "    Mirror app/modules/user/repository.py: take a session, return\n"
        "    models or None, and keep business logic out of this layer.\n"
        '    """\n\n'
        "    def __init__(self, session: AsyncSession) -> None:\n"
        '        """Store the database session.\n\n'
        "        Args:\n"
        "            session: The async database session for all queries.\n"
        '        """\n'
        "        self.session = session\n"
    )


def _service_stub(module: str) -> str:
    """Return the ``service.py`` stub for a module."""
    cls = class_name(module)
    return (
        f'"""Business-logic layer for the {module} module."""\n\n'
        f"from app.modules.{module}.repository import {cls}Repository\n\n\n"
        f"class {cls}Service:\n"
        f'    """Business-logic layer for {cls} operations."""\n\n'
        f"    def __init__(self, repository: {cls}Repository) -> None:\n"
        '        """Inject the repository used for all persistence.\n\n'
        "        Args:\n"
        f"            repository: The {cls}Repository to delegate to.\n"
        '        """\n'
        "        self.repository = repository\n"
    )


def _test_routes_stub(module: str, collection: str) -> str:
    """Return the ``test_routes.py`` skeleton for a module."""
    return (
        f'"""Tests for the {module} routes."""\n\n'
        f"from app.modules.{module} import router\n\n\n"
        f"def test_{collection}_router_has_prefix() -> None:\n"
        '    """The scaffolded router is mounted under its prefix."""\n'
        f'    assert router.prefix == "/{collection}"\n'
    )


def validate_module_name(module: str) -> str:
    """Validate and return a feature module name.

    Args:
        module: Candidate module package name.

    Returns:
        The validated module name.

    Raises:
        ValueError: If ``module`` is not a snake_case Python package name.
    """
    if not MODULE_RE.fullmatch(module) or "__" in module:
        raise ValueError(
            "module must be a snake_case package name, e.g. product "
            "or order_item"
        )
    return module


def scaffold_module(root: Path, module: str) -> None:
    """Create a feature module and register its router.

    Args:
        root: Repository root.
        module: Valid snake_case module name.

    Raises:
        FileExistsError: If the module package already exists.
        ValueError: If ``module`` is invalid.
    """
    module = validate_module_name(module)
    module_dir = root / "app" / "modules" / module
    test_dir = root / "tests" / "modules" / module

    if module_dir.exists():
        raise FileExistsError(f"module already exists: {module_dir}")

    module_dir.mkdir(parents=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    collection = route_collection_name(module)

    (module_dir / "__init__.py").write_text(
        f"from app.modules.{module}.routes import router\n\n"
        '__all__ = ["router"]\n'
    )
    (module_dir / "routes.py").write_text(
        "from fastapi import APIRouter\n\n"
        f'router = APIRouter(prefix="/{collection}", tags=["{collection}"])\n'
    )

    (module_dir / "models.py").write_text(_models_stub(module))
    (module_dir / "schemas.py").write_text(_schemas_stub(module))
    (module_dir / "exceptions.py").write_text(_exceptions_stub(module))
    (module_dir / "repository.py").write_text(_repository_stub(module))
    (module_dir / "service.py").write_text(_service_stub(module))

    (test_dir / "__init__.py").touch()
    (test_dir / "test_routes.py").write_text(
        _test_routes_stub(module, collection)
    )

    register_router(root / "app" / "api.py", module)


def register_router(api_path: Path, module: str) -> None:
    """Register a module router in ``app/api.py``.

    Args:
        api_path: Path to the API router module.
        module: Valid snake_case module name.
    """
    module = validate_module_name(module)
    lines = api_path.read_text().splitlines()
    import_line = f"from app.modules.{module} import router as {module}_router"
    include_line = f"v1_router.include_router({module}_router)"

    if import_line not in lines:
        import_at = _last_matching_index(lines, "from app.modules.") + 1
        lines.insert(import_at, import_line)

    if include_line not in lines:
        include_at = _last_matching_index(lines, "v1_router.include_router(")
        if include_at == -1:
            include_at = _first_matching_index(lines, "v1_router = APIRouter()")
        lines.insert(include_at + 1, include_line)

    api_path.write_text("\n".join(lines) + "\n")


def route_collection_name(module: str) -> str:
    """Return a route collection name for a module.

    Args:
        module: Valid snake_case module name.

    Returns:
        Pluralized route collection name.
    """
    module = validate_module_name(module)
    parts = module.split("_")
    parts[-1] = _pluralize(parts[-1])
    return "_".join(parts)


def _pluralize(noun: str) -> str:
    """Pluralize a simple English noun for scaffolded route prefixes."""
    if noun.endswith("y") and noun[-2:] not in {"ay", "ey", "iy", "oy", "uy"}:
        return f"{noun[:-1]}ies"
    if noun.endswith(("s", "x", "z", "ch", "sh")):
        return f"{noun}es"
    return f"{noun}s"


def _last_matching_index(lines: list[str], prefix: str) -> int:
    """Return the last line index that starts with ``prefix``."""
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].startswith(prefix):
            return index
    return -1


def _first_matching_index(lines: list[str], text: str) -> int:
    """Return the first line index equal to ``text``."""
    for index, line in enumerate(lines):
        if line == text:
            return index
    return -1


def main() -> None:
    """Run the module scaffolder."""
    parser = argparse.ArgumentParser(
        description="Scaffold a QuoinAPI feature module."
    )
    parser.add_argument("module", help="snake_case feature module name")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    try:
        scaffold_module(root=root, module=args.module)
    except (FileExistsError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(
        f"Module '{args.module}' scaffolded in "
        f"app/modules/{args.module}/ and tests/modules/{args.module}/"
    )
    print(f"Router registered in app/api.py as {args.module}_router")
    print(
        "Stubs (repository, service, schemas, exceptions, skeleton test) "
        "are minimal and pass 'just check' as-is."
    )
    print(
        "models.py is intentionally empty: define a table then run "
        "'just migrate-gen'. See the quoin-new-module skill / "
        "docs/guides/creating-a-module.md to fill in the layers."
    )


if __name__ == "__main__":
    main()
