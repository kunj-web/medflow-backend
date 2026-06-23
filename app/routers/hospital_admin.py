from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/admin/hospital", tags=["hospital admin"])

# Legacy hospital-scoped admin routes are intentionally disabled.
# Marketplace admin workflows now belong in app.routers.admin_review.
