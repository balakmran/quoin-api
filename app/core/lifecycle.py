import asyncio

import anyio


class Lifecycle:
    """Track in-flight requests and coordinate graceful shutdown.

    A single instance lives on ``app.state.lifecycle`` for the lifetime
    of the application. The in-flight counter is maintained by
    ``InFlightRequestMiddleware``; the shutdown drain is driven by the
    lifespan handler in :mod:`app.main`.

    All mutation happens on the single asyncio event loop, so the
    counter needs no lock. The ``_idle`` event is set whenever no
    requests are in flight, letting :meth:`drain` await the moment the
    server is quiet.
    """

    def __init__(self) -> None:
        """Initialize an idle lifecycle with no requests in flight."""
        self._in_flight = 0
        self._shutting_down = False
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def in_flight(self) -> int:
        """Number of requests currently being processed."""
        return self._in_flight

    @property
    def is_shutting_down(self) -> bool:
        """Whether shutdown has begun and readiness should report 503."""
        return self._shutting_down

    def acquire(self) -> None:
        """Mark a request as entering the in-flight set."""
        self._in_flight += 1
        self._idle.clear()

    def release(self) -> None:
        """Mark a request as leaving the in-flight set."""
        self._in_flight -= 1
        if self._in_flight <= 0:
            self._in_flight = 0
            self._idle.set()

    def begin_shutdown(self) -> None:
        """Flag the application as shutting down.

        Once set, the readiness probe returns 503 so orchestrators stop
        routing new traffic to this instance.
        """
        self._shutting_down = True

    async def drain(self, timeout: float) -> bool:
        """Wait for in-flight requests to finish, bounded by ``timeout``.

        Args:
            timeout: Maximum seconds to wait for the in-flight count to
                reach zero. A value ``<= 0`` skips waiting entirely.

        Returns:
            True if the server drained to idle within the timeout (or
            was already idle); False if the timeout elapsed with
            requests still in flight.
        """
        if self._in_flight == 0:
            return True
        if timeout <= 0:
            return self._in_flight == 0
        try:
            with anyio.fail_after(timeout):
                await self._idle.wait()
            return True
        except TimeoutError:
            return False


__all__ = ["Lifecycle"]
