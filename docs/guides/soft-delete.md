# Soft Delete

`DELETE /api/v1/users/{id}` does not remove the row. It stamps a
`deleted_at` timestamp — a **tombstone** — and every subsequent read
excludes tombstoned rows. The `user` module is the reference
implementation; mirror it when a resource needs recoverable deletes or an
audit trail of what once existed.

## The model

```python
# Soft-delete tombstone: NULL means live, a timestamp means deleted.
# System-owned (set by delete_user); never exposed or client-settable.
deleted_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
)
```

`deleted_at` is **not** in `UserRead`, `UserCreate`, or `UserUpdate`. It
is set only by the delete path (`UserRepository.delete`, reached through
`UserService.delete_user`), so a client can neither read nor write it
directly.

## `deleted_at` vs `is_active`

The `user` model has both, and they are deliberately independent:

| Field        | Owner  | Meaning                                             |
| :----------- | :----- | :-------------------------------------------------- |
| `is_active`  | client | A business flag (e.g. suspended vs enabled). Set through `UserUpdate`. |
| `deleted_at` | system | A lifecycle tombstone. Set only by `delete_user`.   |

Deleting a user leaves `is_active` untouched — a tombstone is not a
status change. Conflating the two would let a client "delete" a user with
a normal update, which is exactly what we avoid.

## Reads exclude tombstoned rows

Every read path filters `deleted_at IS NULL`:

- `get` / `get_by_email` — a soft-deleted user reads as **404 / absent**.
- `list` — the shared filter drops tombstoned rows from both the page and
  the `total` count.
- Deleting an already-deleted user is a `404`, because `get_user` no
  longer finds it.

## Email reuse and the partial unique index

The case-insensitive unique index on `email` is **partial**:

```sql
CREATE UNIQUE INDEX ix_users_email_lower
  ON users (lower(email)) WHERE deleted_at IS NULL;
```

Without the `WHERE` clause, a soft-deleted row would hold its email
hostage forever, blocking anyone from re-registering it. The partial
index scopes uniqueness to *live* rows, so a tombstoned email is free to
be used again while historical rows keep their original address. The
migration that introduces `deleted_at` also swaps the full index for this
partial one — Alembic autogenerate can't diff the `WHERE` clause on a
functional index, so that step is hand-written in the migration.

## Delete is not a hard delete

Because delete is an `UPDATE` (setting the tombstone) and never a `DELETE`
statement, it cannot raise a foreign-key `IntegrityError`. There is no
"cannot delete: still referenced" (409) path — referencing rows remain
valid, pointing at a row that still exists but reads as deleted.

## Testing

Soft delete is only correct if the tombstone is invisible everywhere a
live row would appear, so assert absence from *both* read paths — the
single fetch and the listing — not just the 204:

```python
async def test_delete_user(admin_client: AsyncClient) -> None:
    """Soft delete hides the user from reads and returns 204."""
    created = await admin_client.post(
        "/api/v1/users/", json={"email": "delete@example.com"}
    )
    user_id = created.json()["id"]

    response = await admin_client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == 204

    fetched = await admin_client.get(f"/api/v1/users/{user_id}")
    assert fetched.status_code == 404

    listing = await admin_client.get("/api/v1/users/?limit=100")
    assert user_id not in [row["id"] for row in listing.json()["items"]]
```

Two further cases catch the mistakes this pattern actually produces.
Deleting twice must return **404, not a second 204** — a repository that
forgets the `deleted_at IS NULL` predicate will happily re-tombstone a
dead row. And the partial unique index must let the address go: register
an email, delete it, and register it again, expecting `201`.
`tests/modules/user/test_routes.py` holds both as
`test_delete_user_twice_returns_404` and
`test_delete_user_frees_email_for_reuse`.

## What's intentionally not here

- **Hard delete / purge** — true removal of tombstoned rows (for GDPR
  Article 17 erasure, for example) is a scheduled retention job the
  deployer owns. The retention period is jurisdiction- and
  business-specific, so the template does not pick one for you. The
  soft-delete tombstone is the hook such a job filters on.
- **Un-delete / restore** — trivial to add (clear `deleted_at`) but left
  out of the template until a resource needs it; mind the partial index
  if the email was re-registered in the meantime.

## See Also

- [Database Migrations](database-migrations.md) — the hand-written step
  that swaps the full unique index for the partial one
- [Creating a Module](creating-a-module.md) — where the repository's
  `deleted_at IS NULL` predicate belongs
- [Testing](testing.md) — the `admin_client` fixture used above
