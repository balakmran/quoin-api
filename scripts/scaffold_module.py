"""Scaffold a QuoinAPI feature module."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MODULE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

FILES = (
    "models.py",
    "schemas.py",
    "repository.py",
    "service.py",
    "exceptions.py",
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

    for filename in FILES:
        (module_dir / filename).touch()

    (test_dir / "__init__.py").touch()
    (test_dir / "test_routes.py").touch()

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


if __name__ == "__main__":
    main()
