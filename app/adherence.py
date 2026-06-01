"""/api/me/adherence endpoint."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from flask import Blueprint, jsonify, request

from . import PATIENT_ID, get_session
from .models import Prescription, Reminder


bp = Blueprint("adherence", __name__, url_prefix="/api/me/adherence")


def _err(msg: str, code: str, status: int):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    return resp


@bp.get("")
def get_adherence():
    try:
        days = int(request.args.get("days", "30"))
    except ValueError:
        days = 30
    if days <= 0 or days > 365:
        days = 30

    session = get_session()
    today = datetime.now(timezone.utc).date()
    window_start = datetime.combine(today - timedelta(days=days - 1), time(0, 0))
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rx_ids = [
        rx.id
        for rx in session.query(Prescription)
        .filter(Prescription.patient_id == PATIENT_ID)
        .all()
    ]

    taken = 0
    skipped = 0
    missed = 0

    if rx_ids:
        reminders = (
            session.query(Reminder)
            .filter(
                Reminder.prescription_id.in_(rx_ids),
                Reminder.scheduled_at >= window_start,
                Reminder.scheduled_at < now + timedelta(days=1),
            )
            .all()
        )
        for r in reminders:
            if r.taken_at is not None:
                taken += 1
            elif r.skipped:
                skipped += 1
            elif r.scheduled_at < now:
                missed += 1

    scheduled_count = taken + skipped + missed
    take_rate = round(taken / max(1, scheduled_count) * 100)

    streak_days = 0
    if rx_ids:
        cursor_day = today - timedelta(days=1)
        for _ in range(365):
            day_start = datetime.combine(cursor_day, time(0, 0))
            day_end = day_start + timedelta(days=1)
            rems = (
                session.query(Reminder)
                .filter(
                    Reminder.prescription_id.in_(rx_ids),
                    Reminder.scheduled_at >= day_start,
                    Reminder.scheduled_at < day_end,
                )
                .all()
            )
            if not rems:
                break
            ok = True
            for r in rems:
                if r.taken_at is None and not r.skipped:
                    ok = False
                    break
            if not ok:
                break
            streak_days += 1
            cursor_day -= timedelta(days=1)

    return jsonify(
        {
            "window_days": days,
            "taken": taken,
            "skipped": skipped,
            "missed": missed,
            "take_rate": take_rate,
            "streak_days": streak_days,
        }
    )
