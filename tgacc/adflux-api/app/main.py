import logging
import time
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import get_settings
from app.database import engine
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.csrf import CSRFMiddleware

from app.auth.routes import router as auth_router
from app.clients.routes import router as clients_router
from app.accounts.routes import router as accounts_router
from app.payments.routes import router as payments_router
from app.chat.routes import router as chat_router
from app.outreach.routes import router as outreach_router
from app.outreach.campaigns import router as campaigns_router, seq_router as sequences_router
from app.outreach.metrics import router as metrics_router
from app.admin.routes import router as admin_router
from app.finance.routes import router as finance_router
from app.tickets.routes import router as tickets_router
from app.orders.routes import router as orders_router
from app.wallet.routes import router as wallet_router
from app.crm.routes import router as crm_router
from app.subscriptions.routes import router as subscriptions_router
from app.alerts.routes import router as alerts_router
from app.affiliate.routes import router as affiliate_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("AdFlux API starting up")
    yield
    await engine.dispose()
    log.info("AdFlux API shut down")


app = FastAPI(
    title="AdFlux API",
    description="AdFlux Ad Account Management Platform API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Auth", "description": "Authentication and authorization"},
        {"name": "Accounts", "description": "Ad account management"},
        {"name": "Wallet", "description": "Multi-currency wallet system"},
        {"name": "Subscriptions", "description": "Subscription plans and billing"},
        {"name": "Affiliate", "description": "Affiliate and referral program"},
        {"name": "CRM", "description": "Customer relationship management"},
        {"name": "Facebook", "description": "Facebook/Instagram integration"},
        {"name": "Payments", "description": "Payment processing"},
        {"name": "Finance", "description": "Financial operations (admin)"},
        {"name": "Alerts", "description": "System alerts and notifications"},
        {"name": "Tickets", "description": "Support ticket system"},
        {"name": "Orders", "description": "Order management"},
        {"name": "Chat", "description": "WebSocket chat"},
    ],
)

# --- Rate limiting (slowapi) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# --- Security headers ---
app.add_middleware(SecurityHeadersMiddleware)

# --- CSRF protection ---
app.add_middleware(CSRFMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://admin.adflux.store",
        "https://portal.adflux.store",
        "https://adflux.store",
        "https://www.adflux.store",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "ngrok-skip-browser-warning", "X-CSRF-Token"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log.info(f"{request.method} {request.url.path} → {response.status_code} ({duration:.3f}s)")
    return response


app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(accounts_router)
app.include_router(payments_router)
app.include_router(chat_router)
app.include_router(outreach_router)
app.include_router(campaigns_router)
app.include_router(sequences_router)
app.include_router(metrics_router)
app.include_router(admin_router)
app.include_router(finance_router)
app.include_router(tickets_router)
app.include_router(orders_router)
app.include_router(crm_router)
app.include_router(wallet_router)
app.include_router(subscriptions_router)
app.include_router(alerts_router)
app.include_router(affiliate_router)


@app.get("/")
async def root():
    return {"service": "AdFlux Media API", "version": "1.0.0", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with clean messages."""
    errors = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"], "type": error["type"]})
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors}
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database constraint violations."""
    log.error(f"Database integrity error: {exc}")
    detail = "A database constraint was violated"
    if "unique" in str(exc).lower():
        detail = "A record with this value already exists"
    return JSONResponse(status_code=409, content={"detail": detail})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general database errors."""
    log.error(f"Database error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "A database error occurred"})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    log.error(f"Unhandled error on {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred"})
