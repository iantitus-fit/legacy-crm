import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal
from app.routers.ai_actions import router as ai_actions_router
from app.routers.ai_chat import router as ai_chat_router
from app.routers.briefing_admin import router as briefing_admin_router
from app.routers.appointments import router as appointments_router
from app.routers.auth import router as auth_router
from app.routers.automation import router as automation_router
from app.routers.change_orders import router as change_orders_router
from app.routers.change_order_portal import router as change_order_portal_router
from app.routers.calendar import router as calendar_router
from app.routers.contacts import router as contacts_router
from app.routers.contact_import import router as contact_import_router
from app.routers.crews import router as crews_router
from app.routers.dashboard import router as dashboard_router
from app.routers.documents import router as documents_router
from app.routers.employees import router as employees_router
from app.routers.estimate_templates import router as estimate_templates_router
from app.routers.customer_portal import router as customer_portal_router
from app.routers.estimate_email import router as estimate_email_router
from app.routers.estimate_export import router as estimate_export_router
from app.routers.estimates import router as estimates_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router
from app.routers.jobs import router as jobs_router
from app.routers.tasks import router as tasks_router
from app.routers.leads import router as leads_router
from app.routers.materials import router as materials_router
from app.routers.notes import router as notes_router
from app.routers.price_lists import router as price_lists_router
from app.routers.pipeline import router as pipeline_router
from app.routers.pipeline_stages import router as pipeline_stages_router
from app.routers.pipelines import router as pipelines_router
from app.routers.reports import router as reports_router
from app.routers.sms import router as sms_router
from app.routers.sms_webhooks import router as sms_webhooks_router
from app.routers.work_orders import router as work_orders_router
from app.routers.booking import router as booking_router
from app.services.automation_scheduler import start_scheduler
from app.services.pipeline_seed import seed_automations, seed_pipelines

logger = logging.getLogger("legacy_crm")


def run_migrations():
    """Run Alembic migrations on startup so the DB schema is always current."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running database migrations...")
    run_migrations()
    logger.info("Migrations complete.")
    db = SessionLocal()
    try:
        seed_pipelines(db)
        seed_automations(db)
    finally:
        db.close()

    # Sprint 19b — automation scheduler runs as a background asyncio task.
    scheduler_task = start_scheduler()
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except Exception:
            pass


app = FastAPI(title="Legacy CRM", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions with a full traceback before returning 500.

    Without this, gunicorn's worker swallows the error and the client gets
    FastAPI's opaque default 500 — useless for production debugging.
    """
    logger.error(
        "Unhandled exception on %s %s: %s", request.method, request.url, exc
    )
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500, content={"detail": "Internal Server Error"}
    )

app.include_router(ai_actions_router)
app.include_router(ai_chat_router)
app.include_router(briefing_admin_router)
app.include_router(appointments_router)
app.include_router(auth_router)
app.include_router(automation_router)
app.include_router(change_orders_router)
app.include_router(change_order_portal_router)
app.include_router(calendar_router)
app.include_router(contacts_router)
app.include_router(contact_import_router)
app.include_router(crews_router)
app.include_router(dashboard_router)
app.include_router(employees_router)
app.include_router(pipeline_stages_router)
app.include_router(pipelines_router)
app.include_router(jobs_router)
app.include_router(leads_router)
app.include_router(notes_router)
app.include_router(pipeline_router)
app.include_router(estimate_templates_router)
app.include_router(estimates_router)
app.include_router(estimate_export_router)
app.include_router(invoices_router)
app.include_router(payments_router)
app.include_router(estimate_email_router)
app.include_router(customer_portal_router)
app.include_router(materials_router)
app.include_router(price_lists_router)
app.include_router(tasks_router)
app.include_router(documents_router)
app.include_router(reports_router)
app.include_router(sms_router)
app.include_router(sms_webhooks_router)
app.include_router(work_orders_router)
app.include_router(booking_router)


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Production: serve built React frontend
FRONTEND_BUILD_DIR = Path(__file__).resolve().parent.parent / "frontend_build"

if FRONTEND_BUILD_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "assets")), name="frontend_assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Serve React app for client-side routing. API routes are handled above."""
        file_path = FRONTEND_BUILD_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_BUILD_DIR / "index.html"))
