"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _to_dict(ann: dict) -> dict:
    """Convert a MongoDB announcement document to a JSON-serializable dict."""
    ann = dict(ann)
    ann["id"] = str(ann.pop("_id"))
    return ann


def _get_status(ann: dict) -> str:
    """Return 'active', 'upcoming', or 'expired' for an announcement."""
    today = date.today().isoformat()
    end = ann.get("end_date", "")
    start = ann.get("start_date") or None

    if end < today:
        return "expired"
    if start and start > today:
        return "upcoming"
    return "active"


def _require_teacher(teacher_username: str) -> dict:
    """Verify teacher exists; raise 401 otherwise."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements():
    """Return all currently active announcements (public endpoint)."""
    today = date.today().isoformat()
    query = {
        "end_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": today}},
        ],
    }
    results = announcements_collection.find(query).sort("created_at", 1)
    return [_to_dict(a) for a in results]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)):
    """Return all announcements regardless of date (requires authentication)."""
    _require_teacher(teacher_username)
    results = announcements_collection.find().sort("end_date", -1)
    announcements = []
    for a in results:
        d = _to_dict(a)
        d["status"] = _get_status(d)
        announcements.append(d)
    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    end_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...),
):
    """Create a new announcement (requires authentication)."""
    _require_teacher(teacher_username)

    # Validate dates
    try:
        date.fromisoformat(end_date)
        if start_date:
            date.fromisoformat(start_date)
            if start_date > end_date:
                raise HTTPException(
                    status_code=400,
                    detail="Start date must be before expiration date",
                )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
        )

    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    ann = {
        "message": message,
        "start_date": start_date or None,
        "end_date": end_date,
        "created_by": teacher_username,
        "created_at": datetime.utcnow().isoformat(),
    }
    result = announcements_collection.insert_one(ann)
    ann["id"] = str(result.inserted_id)
    ann.pop("_id", None)
    ann["status"] = _get_status(ann)
    return ann


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    end_date: str,
    start_date: Optional[str] = None,
    teacher_username: str = Query(...),
):
    """Update an existing announcement (requires authentication)."""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    try:
        date.fromisoformat(end_date)
        if start_date:
            date.fromisoformat(start_date)
            if start_date > end_date:
                raise HTTPException(
                    status_code=400,
                    detail="Start date must be before expiration date",
                )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
        )

    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    result = announcements_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "message": message,
                "start_date": start_date or None,
                "end_date": end_date,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    ann = announcements_collection.find_one({"_id": oid})
    d = _to_dict(ann)
    d["status"] = _get_status(d)
    return d


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...),
):
    """Delete an announcement (requires authentication)."""
    _require_teacher(teacher_username)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
