from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models import SubscriptionPlan

log = logging.getLogger(__name__)

DEFAULT_PLANS = [
    {
        "name": "Single Platform",
        "slug": "single-platform",
        "description": "Manage ad accounts on one platform with competitive rates.",
        "price_monthly": Decimal("300"),
        "price_semiannual": Decimal("1440"),
        "price_annual": Decimal("2280"),
        "platforms": ["meta"],
        "max_accounts": None,
        "cashback_percent": Decimal("3"),
        "features": [
            "1 ad platform",
            "Unlimited accounts",
            "Priority support",
            "Cashback rewards",
        ],
        "is_active": True,
        "sort_order": 1,
    },
    {
        "name": "All Platforms",
        "slug": "all-platforms",
        "description": "Full access to every supported ad platform.",
        "price_monthly": Decimal("600"),
        "price_semiannual": Decimal("2880"),
        "price_annual": Decimal("5760"),
        "platforms": ["meta", "google", "tiktok", "snapchat", "twitter"],
        "max_accounts": None,
        "cashback_percent": Decimal("5"),
        "features": [
            "All ad platforms",
            "Unlimited accounts",
            "Dedicated account manager",
            "Priority support",
            "Higher cashback",
        ],
        "is_active": True,
        "sort_order": 2,
    },
    {
        "name": "Enterprise",
        "slug": "enterprise",
        "description": "Custom pricing for high-volume advertisers. Contact us for a quote.",
        "price_monthly": Decimal("0"),
        "price_semiannual": None,
        "price_annual": None,
        "platforms": ["meta", "google", "tiktok", "snapchat", "twitter"],
        "max_accounts": None,
        "cashback_percent": Decimal("7"),
        "features": [
            "All ad platforms",
            "Unlimited accounts",
            "Dedicated account manager",
            "Custom commission rates",
            "SLA guarantees",
            "API access",
        ],
        "is_active": True,
        "sort_order": 3,
    },
]


async def seed_plans(db: AsyncSession) -> None:
    """Insert default subscription plans if they don't already exist."""
    for plan_data in DEFAULT_PLANS:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == plan_data["slug"])
        )
        if result.scalar_one_or_none():
            log.info("Plan '%s' already exists, skipping", plan_data["slug"])
            continue
        plan = SubscriptionPlan(**plan_data)
        db.add(plan)
        log.info("Seeded plan '%s'", plan_data["name"])
    await db.commit()
