"""Liveness and dependency readiness endpoints."""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException, status


def create_health_router(
    readiness_check: Callable[[], bool] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["health"])
    check = readiness_check or (lambda: True)

    @router.get("/health")
    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        """Report that the API process can serve requests."""
        return {"status": "ok"}

    @router.get("/health/ready")
    async def readiness() -> dict[str, str]:
        """Report whether required persistence is reachable."""
        try:
            ready = check()
        except Exception:
            ready = False
        if not ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            )
        return {"status": "ok"}

    return router


router = create_health_router()
