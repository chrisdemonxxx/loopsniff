"""Combined AI Tools router — aggregates all AI sub-module routers."""

from fastapi import APIRouter

from app.ai.compliance import router as compliance_router
from app.ai.creative import router as creative_router
from app.ai.landing_page import router as landing_page_router
from app.ai.rag import router as rag_router

router = APIRouter(prefix="/ai", tags=["AI Tools"])

router.include_router(compliance_router)
router.include_router(creative_router)
router.include_router(landing_page_router)
router.include_router(rag_router)
