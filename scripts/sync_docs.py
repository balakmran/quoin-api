#!/usr/bin/env python3
"""Sync project documentation files from root to docs/project/.

This script copies CONTRIBUTING.md, CHANGELOG.md, ROADMAP.md, and LICENSE
from the project root to docs/project/, adjusting image paths as needed.
"""

import re
from pathlib import Path


def adjust_image_paths(content: str, from_root: bool = True) -> str:
    """Adjust image paths for documentation.

    Args:
        content: Markdown content
        from_root: True if converting from root->docs, False for reverse

    Returns:
        Content with adjusted paths
    """
    if from_root:
        # Root -> Docs: ./docs/assets/... -> ../assets/...
        content = re.sub(r"\(\.\/docs\/assets\/", r"(../assets/", content)
    else:
        # Docs -> Root: ../assets/... -> ./docs/assets/...
        content = re.sub(r"\(\.\.\/assets\/", r"(./docs/assets/", content)

    return content


def sync_file(source: Path, dest: Path, adjust_paths: bool = False) -> None:
    """Sync a single file from source to destination.

    Args:
        source: Source file path
        dest: Destination file path
        adjust_paths: Whether to adjust image paths
    """
    if not source.exists():
        print(f"Source not found: {source}")
        return

    content = source.read_text()

    if adjust_paths:
        content = adjust_image_paths(content, from_root=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content)
    print(f"Synced: {source.name} -> {dest.relative_to(Path.cwd())}")


def main() -> None:
    """Sync all project documentation files."""
    root = Path(__file__).parent.parent
    docs_project = root / "docs" / "project"

    print("Syncing project documentation files...\n")

    # Files to sync (source, dest, adjust_image_paths)
    files = [
        (
            root / "CONTRIBUTING.md",
            docs_project / "contributing.md",
            True,  # Adjust image paths
        ),
        (root / "CHANGELOG.md", docs_project / "changelog.md", False),
        (root / "ROADMAP.md", docs_project / "roadmap.md", False),
        (root / "LICENSE", docs_project / "license.md", False),
    ]

    for source, dest, adjust_paths in files:
        sync_file(source, dest, adjust_paths)

    print("\nDocumentation sync complete!")


if __name__ == "__main__":
    main()
