"""
Access control routes (read-only for now):
  GET /access/zones      — list physical access zones
  GET /access/profiles   — list access profiles (zone bundles)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.models.access import AccessZone, AccessProfile
from app.core.dependencies import require_any_role

router = APIRouter(prefix="/access", tags=["access"])


@router.get("/zones")
def list_zones(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_any_role),
):
    zones = db.query(AccessZone).filter(AccessZone.is_active == True).order_by(AccessZone.sort_order).all()
    return [
        {
            "id": str(z.id),
            "code": z.code,
            "name": z.name,
            "description": z.description,
            "floor": z.floor,
        }
        for z in zones
    ]


@router.get("/profiles")
def list_profiles(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_any_role),
):
    profiles = db.query(AccessProfile).filter(AccessProfile.is_active == True).order_by(AccessProfile.name).all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "zone_count": len(p.profile_zones),
        }
        for p in profiles
    ]
