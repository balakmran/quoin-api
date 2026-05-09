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
    <p>FastAPI, asyncpg, and Pydantic v2 — built for production-grade throughput from day one.</p>
  </div>

  <!-- Row 1, col 3: Database Native -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/postgresql/38bdf8" alt="PostgreSQL">
    <span class="quoin-bento__label">ORM · Migrations</span>
    <h2>Database Native</h2>
    <p>PostgreSQL with SQLModel ORM and Alembic migrations pre-wired.</p>
  </div>

  <!-- Row 1, col 4: Strict Quality -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/ruff/38bdf8" alt="Ruff">
    <span class="quoin-bento__label">Zero compromise</span>
    <h2>Strict Quality</h2>
    <p>ty, Ruff, and Pytest enforced on every commit via pre-commit hooks.</p>
  </div>

  <!-- Row 2, col 1: Observable -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/opentelemetry/38bdf8" alt="OpenTelemetry">
    <span class="quoin-bento__label">Built-in</span>
    <h2>Observable</h2>
    <p>Distributed tracing with OpenTelemetry and structured logs with Structlog.</p>
  </div>

  <!-- Row 2, col 2: Tooling -->
  <div class="quoin-bento__tile">
    <img class="quoin-bento__icon-logo" src="https://cdn.simpleicons.org/uv/38bdf8" alt="uv">
    <span class="quoin-bento__label">DX-first</span>
    <h2>Modern Tooling</h2>
    <p>uv, just, prek, and Docker — fast installs, task runner, hooks, and shipping.</p>
  </div>

  <!-- Row 2, col 3-4: Ship on Day One (wide) -->
  <div class="quoin-bento__tile quoin-bento__tile--wide">
    <svg class="quoin-bento__icon-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>
    <span class="quoin-bento__label">Golden Path</span>
    <h2>Ship on Day One</h2>
    <p>Copier scaffolds auth, migrations, observability, CI, and Docker before you write a line of business logic.</p>
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
