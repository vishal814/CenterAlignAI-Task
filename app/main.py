from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.db.database import init_db
from app.db.seed import seed_database
from app.api.routes import router as enterprise_router
from app.api.approval_routes import router as approval_router
from app.api.task_routes import router as task_router
from app.tools.browser_tools import inspect_ticket_in_browser, resolve_ticket_in_browser

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database exists and is seeded
    db_file = Path(settings.DATABASE_PATH)
    if not db_file.exists():
        seed_database(settings.DATABASE_PATH)
    else:
        init_db(settings.DATABASE_PATH)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="CentrAlign AI Operator - Autonomous Enterprise AI Employee Prototype",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(enterprise_router)
app.include_router(approval_router)
app.include_router(task_router)

# Mount Portal Static Files
portal_dir = Path(__file__).resolve().parent.parent / "mock_portal"
app.mount("/portal-static", StaticFiles(directory=str(portal_dir)), name="portal-static")

# Mount Dashboard Frontend Static Files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
frontend_dir.mkdir(parents=True, exist_ok=True)
app.mount("/dashboard-static", StaticFiles(directory=str(frontend_dir)), name="dashboard-static")

@app.get("/api/system/status")
def get_system_status():
    import os
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    has_key = bool(api_key and api_key.strip())
    return {
        "provider": "Google Gemini" if has_key else "Deterministic Fallback Engine",
        "model": settings.GEMINI_MODEL,
        "mode": "Live API" if has_key else "Offline / Deterministic Fallback",
        "hasKey": has_key,
        "autoRefundThreshold": settings.AUTO_REFUND_THRESHOLD
    }

# Routes for UI Pages
@app.get("/portal", response_class=FileResponse)
def get_support_portal():
    portal_index = portal_dir / "index.html"
    return FileResponse(str(portal_index))

@app.get("/", response_class=FileResponse)
def get_dashboard():
    dashboard_index = frontend_dir / "index.html"
    if dashboard_index.exists():
        return FileResponse(str(dashboard_index))
    return HTMLResponse("<h1>CentrAlign AI Operator API Running</h1><p>Visit <a href='/portal'>/portal</a> or check docs at <a href='/docs'>/docs</a>.</p>")

# Browser Automation Interactive Endpoints
class BrowserInspectRequest(BaseModel):
    ticket_id: str
    portal_url: Optional[str] = None

class BrowserResolveRequest(BaseModel):
    ticket_id: str
    notes: str
    portal_url: Optional[str] = None

@app.post("/api/browser/inspect")
def browser_inspect(req: BrowserInspectRequest):
    result = inspect_ticket_in_browser(req.ticket_id, req.portal_url)
    return result

@app.post("/api/browser/resolve")
def browser_resolve(req: BrowserResolveRequest):
    result = resolve_ticket_in_browser(req.ticket_id, req.notes, req.portal_url)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
