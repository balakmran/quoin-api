# Quality Checks

This guide covers the quality assurance tools and workflows to ensure code quality before committing changes.

---

## Overview

The project uses a comprehensive suite of automated tools to maintain code quality:

- **Formatting**: [Ruff](https://github.com/astral-sh/ruff) formatter
- **Linting**: [Ruff](https://github.com/astral-sh/ruff) linter
- **Type Checking**: `ty` static type checker
- **Testing**: [Pytest](https://docs.pytest.org/) with coverage

---

## Running All Checks

Run **all** quality checks with a single command:

```bash
just check
```

This command runs all checks in sequence:

1. **Format** → Auto-fixes code style
2. **Lint** → Checks for code issues
3. **Typecheck** → Verifies type annotations
4. **Test** → Runs test suite with coverage

If all checks pass, you'll see:

```
All checks passed!
```

---

## Individual Checks

### Format Code

```bash
just format
```

Automatically formats all Python files using Ruff.

**What it fixes**:

- Line length (max 80 characters)
- Import ordering
- Trailing whitespace
- Quote normalization

### Lint Code

```bash
just lint
```

Checks for code quality issues without modifying files.

**What it checks**:

- Unused imports
- Undefined variables
- Style violations
- Complexity issues

### Type Check

```bash
just typecheck
```

Validates all type annotations using `ty`.

**Requirements**:

- 100% type hint coverage
- No type errors
- Proper return types

### Run Tests

```bash
just test
```

Runs the full test suite with coverage reporting.

**Requirements**:

- All tests pass
- Coverage ≥ 95%

---

## Pre-commit Hooks

Install pre-commit hooks to run checks automatically before every commit:

```bash
just pi  # Install hooks
```

After installation, hooks run automatically:

```bash
git commit -m "feat: add new feature"
# → Runs format, lint, typecheck automatically
```

To run hooks manually on all files:

```bash
just pr  # Run pre-commit on all files
```

---

## CI Integration

All quality checks run automatically on every push via GitHub Actions:

```yaml
# .github/workflows/ci.yml
- name: Run all quality checks
  run: just check

- name: Verify coverage threshold
  run: coverage report --fail-under=95
```

Pull requests cannot be merged until all checks pass ✅

---

## Quality Standards

The project maintains strict quality standards:

| Check           | Requirement    | Tool   |
| --------------- | -------------- | ------ |
| **Formatting**  | 100% compliant | Ruff   |
| **Linting**     | 0 violations   | Ruff   |
| **Type Hints**  | 100% coverage  | ty     |
| **Tests**       | ≥95% coverage  | Pytest |
| **Line Length** | ≤80 chars      | Ruff   |

---

## Quick Reference

| Task           | Command          |
| -------------- | ---------------- |
| Run all checks | `just check`     |
| Format code    | `just format`    |
| Lint code      | `just lint`      |
| Type check     | `just typecheck` |
| Run tests      | `just test`      |
| Install hooks  | `just pi`        |
| Run hooks      | `just pr`        |
| Sync `main` after a merge | `just sync-main` |

---

## Troubleshooting

### Format Conflicts

If Ruff format changes conflict with manual edits:

```bash
# Reformat everything
just format
```

### Type Errors

If type checking fails:

1. Check return types include `| None` where needed
2. Add type parameters to generics: `list[User]`
3. Use `from __future__ import annotations` for forward refs

### Coverage Below Threshold

If coverage drops below 95%:

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

Find untested lines and add tests.

---

## See Also

- [Testing Guide](testing.md) — Writing and running tests
- [Troubleshooting](troubleshooting.md) — Common quality check issues
- [Contributing Guide](../project/contributing.md) — Development workflow
