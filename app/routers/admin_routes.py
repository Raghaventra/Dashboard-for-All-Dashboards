"""Admin area: manage dashboards, manage users/roles, view recent activity.

All routes here require an admin user (require_admin dependency).
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import require_admin
from app.database import get_db
from app.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    ActivityLog,
    Dashboard,
    User,
)
from app.templating import page_context, templates

router = APIRouter(prefix="/admin")


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.get("")
def admin_home(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    pending = (
        db.query(Dashboard)
        .filter(Dashboard.status == STATUS_PENDING)
        .order_by(Dashboard.created_at.desc())
        .all()
    )
    dashboards = (
        db.query(Dashboard)
        .filter(Dashboard.status != STATUS_PENDING)
        .order_by(Dashboard.sort_order, Dashboard.name)
        .all()
    )
    users = db.query(User).order_by(User.created_at.desc()).all()
    recent = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).limit(50).all()
    return templates.TemplateResponse(
        "admin.html",
        page_context(
            request,
            user=admin,
            pending=pending,
            dashboards=dashboards,
            users=users,
            recent=recent,
        ),
    )


# --------------------------- Approvals ------------------------------------- #
@router.post("/dashboards/{dashboard_id}/approve")
def approve_dashboard(
    dashboard_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        dashboard.status = STATUS_APPROVED
        db.commit()
        log_activity(db, "admin_approve_dashboard", user=admin, detail=dashboard.name, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


@router.post("/dashboards/{dashboard_id}/reject")
def reject_dashboard(
    dashboard_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        dashboard.status = STATUS_REJECTED
        db.commit()
        log_activity(db, "admin_reject_dashboard", user=admin, detail=dashboard.name, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


# --------------------------- Dashboards CRUD ------------------------------- #
@router.post("/dashboards/create")
def create_dashboard(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    description: str = Form(""),
    icon: str = Form(""),
    category: str = Form(""),
    sort_order: int = Form(0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dashboard = Dashboard(
        name=name.strip(),
        url=url.strip(),
        description=description.strip() or None,
        icon=icon.strip() or None,
        category=category.strip() or None,
        sort_order=sort_order,
        is_active=True,
        status=STATUS_APPROVED,  # admin-added tiles are live immediately
        submitted_by=admin.username,
    )
    db.add(dashboard)
    db.commit()
    log_activity(db, "admin_create_dashboard", user=admin, detail=dashboard.name, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


@router.post("/dashboards/{dashboard_id}/update")
def update_dashboard(
    dashboard_id: int,
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    description: str = Form(""),
    icon: str = Form(""),
    category: str = Form(""),
    sort_order: int = Form(0),
    is_active: str = Form("on"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        dashboard.name = name.strip()
        dashboard.url = url.strip()
        dashboard.description = description.strip() or None
        dashboard.icon = icon.strip() or None
        dashboard.category = category.strip() or None
        dashboard.sort_order = sort_order
        dashboard.is_active = is_active == "on"
        db.commit()
        log_activity(db, "admin_update_dashboard", user=admin, detail=dashboard.name, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


@router.post("/dashboards/{dashboard_id}/delete")
def delete_dashboard(
    dashboard_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        name = dashboard.name
        db.delete(dashboard)
        db.commit()
        log_activity(db, "admin_delete_dashboard", user=admin, detail=name, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


# ----------------------------- Users / roles ------------------------------ #
@router.post("/users/{user_id}/set-admin")
def set_admin(
    user_id: int,
    request: Request,
    make_admin: str = Form("on"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target:
        target.is_admin = make_admin == "on"
        db.commit()
        action = "admin_grant" if target.is_admin else "admin_revoke"
        log_activity(db, action, user=admin, detail=target.username or target.email, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)


@router.post("/users/{user_id}/set-active")
def set_active(
    user_id: int,
    request: Request,
    make_active: str = Form("on"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.query(User).filter(User.id == user_id).first()
    # Don't let an admin disable their own account by accident.
    if target and target.id != admin.id:
        target.is_active = make_active == "on"
        db.commit()
        action = "user_enable" if target.is_active else "user_disable"
        log_activity(db, action, user=admin, detail=target.username or target.email, ip_address=_ip(request))
    return RedirectResponse("/admin", status_code=303)
