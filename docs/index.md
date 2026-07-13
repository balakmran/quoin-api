---
title: Home
hide:
  - navigation
  - toc
  - footer
---

<div class="quoin-home" markdown="0">

<canvas id="quoin-bg-canvas" aria-hidden="true"></canvas>

<section class="quoin-hero">
  <span class="quoin-hero__eyebrow">QuoinAPI</span>
  <h1 class="quoin-hero__title">The Foundation for your<br>Python backend API</h1>

  <p class="quoin-hero__tagline">
    Built for teams who ship, not configure.
  </p>

  <div class="quoin-hero__cta">
    <div class="quoin-cli">
      <span class="quoin-cli__cmd">uvx copier copy --trust gh:balakmran/quoin-api my-api</span>
      <button class="quoin-cli__copy" aria-label="Copy command">
        <svg class="quoin-cli__copy-icon" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
        </svg>
        <svg class="quoin-cli__copy-check" hidden xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </button>
    </div>
    <div class="quoin-hero__cta-buttons">
      <a href="guides/getting-started/" class="md-button md-button--primary">Get started</a>
    </div>
  </div>
</section>

<section class="quoin-bento">

  <!-- Row 1, col 1-2: High Performance (wide) -->
  <div class="quoin-bento__tile quoin-bento__tile--wide">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/fastapi/38bdf8" alt="FastAPI">
    <span class="quoin-bento__label">Async-first</span>
    <h2>High Performance</h2>
    <p>FastAPI on asyncpg with Pydantic v2 — async top to bottom, from route to query.</p>
  </div>

  <!-- Row 1, col 3: Database Native -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/postgresql/38bdf8" alt="PostgreSQL">
    <span class="quoin-bento__label">ORM · Migrations</span>
    <h2>Database Native</h2>
    <p>PostgreSQL with SQLModel and Alembic migrations, pre-wired.</p>
  </div>

  <!-- Row 1, col 4: Observable -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/opentelemetry/38bdf8" alt="OpenTelemetry">
    <span class="quoin-bento__label">Built-in</span>
    <h2>Observable</h2>
    <p>OpenTelemetry traces and Structlog logs, auto-correlated by trace and request ID.</p>
  </div>

  <!-- Row 2, col 1: Secure by Default -->
  <div class="quoin-bento__tile">
    <svg class="quoin-bento__icon-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/><circle cx="12" cy="15.25" r="1.4"/></svg>
    <span class="quoin-bento__label">JWT · RBAC</span>
    <h2>Secure by Default</h2>
    <p>Per-route RBAC with JWKS-validated JWTs — a mock OAuth server for local dev.</p>
  </div>

  <!-- Row 2, col 2: Strict Quality -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/ruff/38bdf8" alt="Ruff">
    <span class="quoin-bento__label">Zero compromise</span>
    <h2>Strict Quality</h2>
    <p>ty, Ruff, and Pytest gate every commit and push — 100% type and test coverage.</p>
  </div>

  <!-- Row 2, col 3: Tooling -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/uv/38bdf8" alt="uv">
    <span class="quoin-bento__label">DX-first</span>
    <h2>Modern Tooling</h2>
    <p>uv, just, prek, and Docker — installs, task runner, git hooks, and containers.</p>
  </div>

  <!-- Row 2, col 4: Docs Built-In -->
  <div class="quoin-bento__tile">
    <svg class="quoin-bento__icon-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5c2-1.2 4.5-1.2 8 0 3.5-1.2 6-1.2 8 0v13c-2-1.2-4.5-1.2-8 0-3.5-1.2-6-1.2-8 0V5Z"/><path d="M12 5v13"/></svg>
    <span class="quoin-bento__label">Docs-as-Code</span>
    <h2>Docs Built-In</h2>
    <p>Guides, API reference, and this page ship from the repo to GitHub Pages on every merge.</p>
  </div>

  <!-- Row 3, col 1-2: Ship on Day One (wide) -->
  <div class="quoin-bento__tile quoin-bento__tile--wide">
    <svg class="quoin-bento__icon-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>
    <span class="quoin-bento__label">Golden Path</span>
    <h2>Ship on Day One</h2>
    <p>One Copier command scaffolds the whole stack — auth, database, observability, CI, and Docker — so day one is business logic, not setup.</p>
  </div>

  <!-- Row 3, col 3-4: Built for AI-Native Development (wide) -->
  <div class="quoin-bento__tile quoin-bento__tile--wide">
    <svg class="quoin-bento__icon-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="m7 9 3 3-3 3"/><path d="M12 15h5"/></svg>
    <span class="quoin-bento__label">Claude Code</span>
    <h2>Built for AI-Native Development</h2>
    <p>Skills, subagents, hooks, and MCP servers (context7, postgres) ship pre-wired — Claude follows this codebase's conventions automatically.</p>
    <div class="quoin-bento__stats">
      <span class="quoin-bento__stat"><b>12</b> Skills</span>
      <span class="quoin-bento__stat"><b>2</b> Subagents</span>
      <span class="quoin-bento__stat"><b>5</b> Plugins</span>
      <span class="quoin-bento__stat"><b>2</b> MCP Servers</span>
    </div>
  </div>

</section>

<section class="quoin-cmds">
  <p class="quoin-cmds__eyebrow">Quick start</p>
  <div class="quoin-cmds__terminal">
    <div class="quoin-cmds__bar">
      <span></span><span></span><span></span>
    </div>
    <ul class="quoin-cmds__list">
      <li>
        <span class="quoin-cmds__prompt">$</span>
        <code>just setup</code>
        <span class="quoin-cmds__comment"># install deps &amp; wire commit hooks</span>
      </li>
      <li>
        <span class="quoin-cmds__prompt">$</span>
        <code>just dev</code>
        <span class="quoin-cmds__comment"># DB + OAuth + migrations + server</span>
      </li>
      <li>
        <span class="quoin-cmds__prompt">$</span>
        <code>just new order</code>
        <span class="quoin-cmds__comment"># scaffold a complete DDD module</span>
      </li>
      <li>
        <span class="quoin-cmds__prompt">$</span>
        <code>just check</code>
        <span class="quoin-cmds__comment"># format → lint → typecheck → test</span>
      </li>
    </ul>
  </div>
</section>

<footer class="quoin-home__footer">
  <p class="quoin-home__footer-copy">
    Built by <a href="https://github.com/balakmran" target="_blank" rel="noopener">balakmran</a>
    &nbsp;·&nbsp; Open Source &nbsp;·&nbsp; MIT License
  </p>
</footer>

</div>
