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
is set only by the service on delete, so a client can neither read nor
write it directly.

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

## What's intentionally not here

- **Hard delete / purge** — true removal of tombstoned rows (for GDPR
  Article 17 erasure, for example) is a scheduled retention job, tracked
  in the [backlog](../project/roadmap.md#backlog). The soft-delete
  tombstone is the hook a future erasure job filters on.
- **Un-delete / restore** — trivial to add (clear `deleted_at`) but left
  out of the template until a resource needs it; mind the partial index
  if the email was re-registered in the meantime.
