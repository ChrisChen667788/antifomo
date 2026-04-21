from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.collector import router as collector_router
from app.api.feedback import router as feedback_router
from app.api.focus_assistant import router as focus_assistant_router
from app.api.items import router as items_router
from app.api.knowledge import router as knowledge_router
from app.api.mobile import router as mobile_router
from app.api.preferences import router as preferences_router
from app.api.sessions import router as sessions_router
from app.api.research import router as research_router
from app.api.system import router as system_router
from app.api.tasks import router as tasks_router
from app.api.workbuddy import router as workbuddy_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.db.sqlite_compat import ensure_sqlite_compat_columns
from app.services.item_processing_runtime import start_item_recovery_worker, stop_item_recovery_worker
from app.services.wechat_pc_agent_daemon import read_wechat_agent_status, start_wechat_agent
from app import models  # noqa: F401


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def startup_init_db() -> None:
    # Zero-dependency local demo mode: auto create schema on SQLite.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_compat_columns(engine)

    if settings.wechat_agent_auto_start:
        status = read_wechat_agent_status()
        if not status.running:
            try:
                start_wechat_agent()
            except Exception:
                # Best-effort startup; keep API available even if desktop automation fails.
                pass

    start_item_recovery_worker()


@app.on_event("shutdown")
def shutdown_background_workers() -> None:
    stop_item_recovery_worker()


app.include_router(items_router)
app.include_router(knowledge_router)
app.include_router(preferences_router)
app.include_router(research_router)
app.include_router(collector_router)
app.include_router(feedback_router)
app.include_router(sessions_router)
app.include_router(focus_assistant_router)
app.include_router(tasks_router)
app.include_router(workbuddy_router)
app.include_router(mobile_router)
app.include_router(system_router)
