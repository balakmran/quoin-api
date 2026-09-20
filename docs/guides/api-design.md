# API Design

Shape what callers see: the failure contract, the concurrency rules,
and how the API changes without breaking them.

- [Error Handling](error-handling.md) — raise domain exceptions and let
  the global handler render RFC 9457 problem documents
- [Optimistic Concurrency](optimistic-concurrency.md) — guard updates
  with ETags and `If-Match`
- [Deprecating Endpoints](deprecating-endpoints.md) — retire a route
  with RFC 8594 headers and a sunset date

The conventions these guides assume — status codes, envelopes, and
naming — are listed in [Conventions](../api/conventions.md).
