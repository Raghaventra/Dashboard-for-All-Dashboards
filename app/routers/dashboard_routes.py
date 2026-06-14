"""Hub home, the Testing page (pending tiles), user submissions, launch logging."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import require_login
from app.database import get_db
from app.models import STATUS_APPROVED, STATUS_PENDING, Dashboard, User
from app.templating import page_context, templates

router = APIRouter()


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _group_by_category(dashboards):
    categories: dict = {}
    for d in dashboards:
        categories.setdefault(d.category or "General", []).append(d)
    return categories


@router.get("/")
def hub(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    dashboards = (
        db.query(Dashboard)
        .filter(Dashboard.is_active == True, Dashboard.status == STATUS_APPROVED)  # noqa: E712
        .order_by(Dashboard.sort_order, Dashboard.name)
        .all()
    )
    pending_count = (
        db.query(Dashboard).filter(Dashboard.status == STATUS_PENDING).count()
    )
    log_activity(db, "view_hub", user=user, ip_address=_ip(request))
    return templates.TemplateResponse(
        "hub.html",
        page_context(
            request,
            user=user,
            categories=_group_by_category(dashboards),
            total=len(dashboards),
            pending_count=pending_count,
        ),
    )


@router.get("/testing")
def testing(request: Request, user: User = Depends(require_login), db: Session = Depends(get_db)):
    """Pending (not-yet-approved) dashboards. Anyone logged in can try them here."""
    pending = (
        db.query(Dashboard)
        .filter(Dashboard.status == STATUS_PENDING)
        .order_by(Dashboard.created_at.desc())
        .all()
    )
    log_activity(db, "view_testing", user=user, ip_address=_ip(request))
    return templates.TemplateResponse(
        "testing.html", page_context(request, user=user, dashboards=pending)
    )


@router.get("/dashboards/submit")
def submit_form(request: Request, user: User = Depends(require_login)):
    return templates.TemplateResponse("submit_dashboard.html", page_context(request, user=user))


@router.post("/dashboards/submit")
def submit_dashboard(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    icon: str = Form(""),
    category: str = Form(""),
    description: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    name = name.strip()
    url = url.strip()

    if not name or not url:
        return templates.TemplateResponse(
            "submit_dashboard.html",
            page_context(request, user=user, error="Name and link are required.",
                         name=name, url=url, icon=icon, category=category, description=description),
            status_code=400,
        )

    dashboard = Dashboard(
        name=name,
        url=url,
        icon=icon.strip() or None,
        category=category.strip() or None,
        description=description.strip() or None,
        status=STATUS_PENDING,
        submitted_by=user.username,
        is_active=True,
    )
    db.add(dashboard)
    db.commit()
    log_activity(db, "submit_dashboard", user=user, detail=f"{name} ({url})", ip_address=_ip(request))
    return RedirectResponse("/testing", status_code=303)


@router.post("/launch/{dashboard_id}")
def launch(
    dashboard_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Record that a user launched a dashboard. The browser opens the tab itself."""
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard is None or not dashboard.is_active:
        return JSONResponse({"ok": False, "error": "Dashboard not found."}, status_code=404)

    where = "testing" if dashboard.status == STATUS_PENDING else "hub"
    log_activity(
        db,
        "launch_dashboard",
        user=user,
        detail=f"{dashboard.name} ({dashboard.url}) [{where}]",
        ip_address=_ip(request),
    )
    return JSONResponse({"ok": True, "url": dashboard.url, "name": dashboard.name})
