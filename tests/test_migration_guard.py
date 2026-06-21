"""Tests for the ``scripts/migration_guard.py`` zero-downtime guard.

The guard parses a generated Alembic script and flags operations that are
unsafe to apply against a live, populated database. These tests pin the
detection rules and the false-positive guards (commented code, Alembic's
``existing_nullable=False`` context, ``server_default`` escape hatch).
"""

from scripts.migration_guard import Flag, scan


def _reasons(src: str) -> list[str]:
    """Return the reason text of every flag raised for ``src``."""
    return [f.reason for f in scan(src)]


def test_clean_migration_has_no_flags():
    """A pure add-nullable-column migration is safe."""
    src = """
def upgrade() -> None:
    op.add_column('users', sa.Column('nickname', sa.String(), nullable=True))
"""
    assert scan(src) == []


def test_drop_column_flagged():
    """Dropping a column is irreversible data loss."""
    src = "def upgrade():\n    op.drop_column('users', 'legacy_token')\n"
    flags = scan(src)
    assert len(flags) == 1
    assert "drops a column" in flags[0].reason


def test_drop_table_flagged():
    """Dropping a table is irreversible data loss."""
    src = "def upgrade():\n    op.drop_table('sessions')\n"
    assert any("drops a table" in r for r in _reasons(src))


def test_drop_constraint_flagged():
    """Dropping a constraint may break a running app's invariants."""
    src = "def upgrade():\n    op.drop_constraint('uq_x', 'users')\n"
    assert any("drops a constraint" in r for r in _reasons(src))


def test_multiline_alter_column_type_change_flagged():
    """Autogenerate emits multi-line calls — the AST scan must catch them."""
    src = """
def upgrade() -> None:
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
"""
    flags = scan(src)
    assert len(flags) == 1
    assert "changes a column type" in flags[0].reason


def test_existing_nullable_false_is_not_a_not_null_flag():
    """``existing_nullable=False`` is context, not a new NOT NULL constraint."""
    src = """
def upgrade() -> None:
    op.alter_column(
        "users",
        "name",
        type_=sa.String(length=100),
        existing_nullable=False,
    )
"""
    reasons = _reasons(src)
    # Flagged for the type change, but never for "sets NOT NULL".
    assert any("changes a column type" in r for r in reasons)
    assert not any("sets NOT NULL" in r for r in reasons)


def test_set_not_null_on_existing_column_flagged():
    """Tightening an existing column to NOT NULL scans and locks the table."""
    src = """
def upgrade():
    op.alter_column("users", "email", nullable=False)
"""
    assert any("sets NOT NULL" in r for r in _reasons(src))


def test_add_not_null_column_without_server_default_flagged():
    """A NOT NULL column with no server_default fails on a populated table."""
    src = """
def upgrade():
    op.add_column("users", sa.Column("age", sa.Integer(), nullable=False))
"""
    assert any(
        "NOT NULL column without a server_default" in r for r in _reasons(src)
    )


def test_add_not_null_column_with_server_default_is_safe():
    """A server_default makes a NOT NULL column safe to add."""
    src = """
def upgrade():
    op.add_column(
        "users",
        sa.Column("flag", sa.Boolean(), nullable=False,
                  server_default="false"),
    )
"""
    assert scan(src) == []


def test_add_not_null_column_with_server_default_none_flagged():
    """An explicit server_default=None supplies no default, so it is unsafe."""
    src = """
def upgrade():
    op.add_column(
        "users",
        sa.Column("role", sa.String(), nullable=False, server_default=None),
    )
"""
    assert any(
        "NOT NULL column without a server_default" in r for r in _reasons(src)
    )


def test_create_index_without_concurrently_flagged():
    """A plain CREATE INDEX takes a blocking write lock."""
    src = "def upgrade():\n    op.create_index('ix_a', 'users', ['a'])\n"
    assert any("without CONCURRENTLY" in r for r in _reasons(src))


def test_create_index_concurrently_is_safe():
    """postgresql_concurrently=True clears the index-build flag."""
    src = (
        "def upgrade():\n    op.create_index('ix_a', 'users', ['a'], "
        "postgresql_concurrently=True)\n"
    )
    assert scan(src) == []


def test_destructive_raw_sql_flagged():
    """Raw SQL containing DELETE FROM / DROP <obj> / TRUNCATE is flagged."""
    for stmt in (
        "DELETE FROM users WHERE x IS NULL",
        "DROP TABLE legacy_sessions",
        "TRUNCATE users",
    ):
        src = f'def upgrade():\n    op.execute("{stmt}")\n'
        assert any("destructive operation" in r for r in _reasons(src)), stmt


def test_non_destructive_raw_sql_not_flagged():
    """A plain UPDATE is not treated as destructive."""
    src = 'def upgrade():\n    op.execute("UPDATE users SET x = 1")\n'
    assert scan(src) == []


def test_destructive_keyword_in_string_data_not_flagged():
    """DROP/DELETE appearing only as data words must not false-positive."""
    src = (
        "def upgrade():\n"
        "    op.execute(\"UPDATE settings SET label = 'Drop-off point'\")\n"
    )
    assert scan(src) == []


def test_batch_alter_table_drop_column_flagged():
    """Destructive ops inside a batch_alter_table block are still caught."""
    src = """
def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("legacy")
"""
    assert any("drops a column" in r for r in _reasons(src))


def test_commented_out_operation_not_flagged():
    """A commented-out op never trips the guard."""
    src = "def upgrade():\n    # op.drop_column('users', 'x')\n    pass\n"
    assert scan(src) == []


def test_unparseable_source_returns_empty():
    """Malformed source degrades gracefully instead of raising."""
    assert scan("def upgrade(:\n    op.drop_table(") == []


def test_flags_sorted_by_line():
    """Flags are returned in source order."""
    src = """
def upgrade():
    op.drop_column("users", "a")
    op.drop_table("old")
"""
    flags = scan(src)
    assert [f.line for f in flags] == sorted(f.line for f in flags)
    assert all(isinstance(f, Flag) for f in flags)
