# Security Policy

QuoinAPI is a Copier **template**: you `copier copy` it and own the
generated code. This policy covers vulnerabilities in the template
itself — the `app/core` infrastructure, the middleware suite, the auth
wiring, the tooling, and the CI/CD configuration this repository ships.
It does **not** cover security issues in your own modules or in how you
deploy a generated project — see [Deployment scope](#deployment-scope)
below.

---

## Supported Versions

QuoinAPI is pre-1.0 and ships as a source template rather than a
published package. Security fixes are applied to:

| Version | Supported |
| :------ | :-------- |
| `main` (latest, unreleased) | Yes |
| Latest tagged release | Yes |
| Older tags | No — rebase your copy onto the latest release |

Because the template is copied rather than depended on, taking a fix
means pulling the change into your generated project (`copier update`,
or cherry-picking the relevant commit). There is no backport of fixes
to superseded tags.

---

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**
Report privately so a fix can ship before the details are public.

1. **Preferred — GitHub private vulnerability reporting.** Go to the
   repository's **Security** tab → **Report a vulnerability**
   ([direct link](https://github.com/balakmran/quoin-api/security/advisories/new)).
   This opens a private advisory visible only to you and the
   maintainers.
2. **Fallback — email.** If you cannot use GitHub advisories, email
   **bala@balakmran.dev** with `SECURITY` in the subject line.

### What to include

A good report lets us reproduce quickly:

- The affected component or file (e.g. `app/core/security.py`,
  a middleware, a workflow) and the version/commit.
- A description of the issue and its security impact.
- Reproduction steps or a proof of concept, if you have one.
- Any suggested remediation.

---

## What to Expect

This is a single-maintainer project; the timelines below are targets,
communicated honestly rather than promised as an SLA:

| Stage | Target |
| :---- | :----- |
| Acknowledgement of your report | within 3 business days |
| Initial assessment / severity triage | within 7 business days |
| Fix or mitigation on `main` | as fast as severity warrants |
| Public disclosure | coordinated with you, after a fix is available |

We follow **coordinated disclosure**: we will keep you updated, credit
you in the advisory and `CHANGELOG.md` unless you prefer to remain
anonymous, and agree a disclosure date with you. Please give us a
reasonable window to ship a fix before disclosing publicly.

---

## Deployment scope

The template ships with production hardening installed and documented,
but a template cannot secure your deployment for you. The following are
**your responsibility as the deployer** and are out of scope for this
policy — they are documented in the guides so the assumptions are
explicit:

- **Edge rate limiting** — the template assumes an upstream limiter
  (gateway, ingress, CDN, or WAF). See
  [Edge rate limiting](docs/guides/deployment.md#edge-rate-limiting).
- **TLS termination** and forwarded-header trust — see
  [Behind a load balancer or reverse proxy](docs/guides/deployment.md#behind-a-load-balancer-or-reverse-proxy).
- **Probe exposure** — `/health` and `/ready` must not be
  internet-routable. See
  [Health Checks](docs/guides/deployment.md#health-checks).
- **Secrets management, OAuth/IdP configuration, and network policy**
  for your environment.

---

## Security posture & receipts

The controls the template does provide, and how they are configured:

- [Security guide](docs/guides/security.md) — CORS hardening, security
  headers, request size caps, request-ID validation, OAuth trust
  anchors and fail-fast, JWKS refresh backoff, and credential
  redaction.
- [Dependency Scanning](docs/guides/dependency-scanning.md) —
  Dependabot and GitHub-native secret scanning; SHA-pinned Actions;
  digest-pinned build tooling.
- [Authentication guide](docs/guides/authentication.md) — OIDC/JWT
  validation and `require_roles` RBAC.
