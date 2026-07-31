from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

from app.api.auth import router as auth_router, users_router  # noqa: E402
from app.api.balance import router as balance_router  # noqa: E402
from app.api.budget import router as budget_router  # noqa: E402
from app.api.categories import router as categories_router  # noqa: E402
from app.api.city_analytics import router as city_analytics_router  # noqa: E402
from app.api.config import router as config_router  # noqa: E402
from app.api.dashboard import router as dashboard_router  # noqa: E402
from app.api.integration import router as integration_router  # noqa: E402
from app.api.movements import router as movements_router  # noqa: E402
from app.api.stops import router as stops_router  # noqa: E402

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(movements_router)
router.include_router(balance_router)
router.include_router(categories_router)
router.include_router(dashboard_router)
router.include_router(city_analytics_router)
router.include_router(budget_router)
router.include_router(integration_router)
router.include_router(stops_router)
router.include_router(config_router)
