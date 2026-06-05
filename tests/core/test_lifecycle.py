import asyncio

import anyio
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.lifecycle import Lifecycle
from app.core.middlewares import InFlightRequestMiddleware


@pytest.mark.asyncio
async def test_lifecycle_starts_idle() -> None:
    """A fresh lifecycle has no requests in flight and is not draining."""
    lifecycle = Lifecycle()

    assert lifecycle.in_flight == 0
    assert lifecycle.is_shutting_down is False


@pytest.mark.asyncio
async def test_acquire_release_track_in_flight() -> None:
    """acquire/release adjust the in-flight counter symmetrically."""
    lifecycle = Lifecycle()

    lifecycle.acquire()
    lifecycle.acquire()
    two_in_flight = 2
    assert lifecycle.in_flight == two_in_flight

    lifecycle.release()
    assert lifecycle.in_flight == 1

    lifecycle.release()
    assert lifecycle.in_flight == 0


@pytest.mark.asyncio
async def test_release_floors_at_zero() -> None:
    """An unbalanced release never drives the counter negative."""
    lifecycle = Lifecycle()

    lifecycle.release()

    assert lifecycle.in_flight == 0


@pytest.mark.asyncio
async def test_begin_shutdown_sets_flag() -> None:
    """begin_shutdown flips the readiness-facing shutdown flag."""
    lifecycle = Lifecycle()

    lifecycle.begin_shutdown()

    assert lifecycle.is_shutting_down is True


@pytest.mark.asyncio
async def test_drain_returns_immediately_when_idle() -> None:
    """Drain succeeds without waiting when nothing is in flight."""
    lifecycle = Lifecycle()

    assert await lifecycle.drain(timeout=5.0) is True


@pytest.mark.asyncio
async def test_drain_waits_for_in_flight_to_finish() -> None:
    """Drain resolves once a concurrent request releases the counter."""
    lifecycle = Lifecycle()
    lifecycle.acquire()

    async def finish_soon() -> None:
        await anyio.sleep(0.05)
        lifecycle.release()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(finish_soon())
        drained = await lifecycle.drain(timeout=5.0)

    assert drained is True
    assert lifecycle.in_flight == 0


@pytest.mark.asyncio
async def test_drain_times_out_when_request_stuck() -> None:
    """Drain returns False when the timeout elapses with work in flight."""
    lifecycle = Lifecycle()
    lifecycle.acquire()

    assert await lifecycle.drain(timeout=0.05) is False
    assert lifecycle.in_flight == 1


@pytest.mark.asyncio
async def test_drain_zero_timeout_does_not_wait() -> None:
    """A non-positive timeout skips waiting and reports the live state."""
    lifecycle = Lifecycle()
    lifecycle.acquire()

    assert await lifecycle.drain(timeout=0) is False


@pytest.fixture
def in_flight_app() -> FastAPI:
    """Minimal app wiring the in-flight middleware to a lifecycle."""
    app = FastAPI()
    app.state.lifecycle = Lifecycle()
    app.add_middleware(InFlightRequestMiddleware)

    @app.get("/slow")
    async def slow_endpoint() -> dict[str, int]:
        await anyio.sleep(0.1)
        return {"in_flight": app.state.lifecycle.in_flight}

    @app.get("/health")
    async def health_endpoint() -> dict[str, int]:
        return {"in_flight": app.state.lifecycle.in_flight}

    return app


@pytest.mark.asyncio
async def test_middleware_counts_in_flight_request(
    in_flight_app: FastAPI,
) -> None:
    """The counter is non-zero while a request is being handled."""
    lifecycle: Lifecycle = in_flight_app.state.lifecycle
    async with AsyncClient(
        transport=ASGITransport(app=in_flight_app), base_url="http://test"
    ) as ac:
        response = await ac.get("/slow")

    # The handler observed itself inside the in-flight set...
    assert response.json()["in_flight"] == 1
    # ...and the counter returned to zero once the response completed.
    assert lifecycle.in_flight == 0


@pytest.mark.asyncio
async def test_middleware_excludes_probe_paths(
    in_flight_app: FastAPI,
) -> None:
    """Probe paths are not counted so they never perturb the drain gauge."""
    async with AsyncClient(
        transport=ASGITransport(app=in_flight_app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")

    assert response.json()["in_flight"] == 0
