# Build

Add a feature to your API: a domain module, the tables behind it, and
the rules that guard access to it.

- [Creating a Module](creating-a-module.md) — scaffold a module and
  register its routes under `/api/v1/`
- [Database Migrations](database-migrations.md) — change a model and
  generate the Alembic script that matches it
- [Authentication](authentication.md) — validate JWTs against your IdP
  and gate routes by role
- [Pagination & Filtering](pagination.md) — return the shared paginated
  envelope from a list endpoint
- [Soft Delete](soft-delete.md) — retire a row without losing it
- [Outbound HTTP Client](outbound-http.md) — call another service
  through the shared retrying client

!!! tip "Start here"
    `just new <module>` scaffolds every file described in
    [Creating a Module](creating-a-module.md). Mirror
    `app/modules/user/`, the worked example, then delete it once you
    have modules of your own.
