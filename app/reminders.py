"""/api/me/reminders/* endpoints. Schedule expansion lives here too."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, jsonify, request

from . import PATIENT_ID, get_session
from .models import Prescription, Reminder


bp = Blueprint("reminders", __name__, url_prefix="/api/me/reminders")


_BLOCKS = [
    ("morning", time(5, 0), time(10, 59, 59)),
    ("midday", time(11, 0), time(14, 59, 59)),
    ("evening", time(15, 0), time(20, 59, 59)),
    ("night_part1", time(21, 0), time(23, 59, 59)),
    ("night_part2", time(0, 0), time(4, 59, 59)),
]

_FREE_TEXT_SLOTS = {
    "morning": time(8, 0),
    "midday": time(12, 0),
    "evening": time(18, 0),
    "night": time(22, 0),
}


def _err(msg: str, code: str, status: int):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    return resp


def expand_schedule_for_day(schedule: str, target_day: date) -> list[datetime]:
    """Return list of naive datetimes (treated as local clock) for a single day."""
    if not schedule:
        return []
    s = schedule.strip().lower()
    if s == "as needed" or s == "":
        return []

    times: list[time] = []

    m = re.fullmatch(r"every\s+(\d+)\s*h", s)
    if m:
        try:
            n = int(m.group(1))
        except ValueError:
            n = 0
        if n <= 0 or n > 24:
            return []
        doses = max(1, 24 // n)
        start_hour = 8
        for i in range(doses):
            hour = (start_hour + i * n) % 24
            times.append(time(hour, 0))
    else:
        for tok in re.split(r"[,/+ ]+", s):
            tok = tok.strip()
            if not tok:
                continue
            slot = _FREE_TEXT_SLOTS.get(tok)
            if slot is not None:
                times.append(slot)

    out: list[datetime] = []
    for t in times:
        out.append(datetime.combine(target_day, t))
    return sorted(set(out))


def _block_of(dt: datetime) -> str:
    t = dt.time()
    if time(5, 0) <= t <= time(10, 59, 59):
        return "morning"
    if time(11, 0) <= t <= time(14, 59, 59):
        return "midday"
    if time(15, 0) <= t <= time(20, 59, 59):
        return "evening"
    return "night"


def _ensure_reminders_for_day(session, target_day: date) -> list[Reminder]:
    """Generate (idempotently) and return reminders for this patient on this date."""
    rxs = (
        session.query(Prescription)
        .filter(Prescription.patient_id == PATIENT_ID, Prescription.active.is_(True))
        .all()
    )

    day_start = datetime.combine(target_day, time(0, 0))
    day_end = day_start + timedelta(days=1)

    for rx in rxs:
        rx_started = rx.started_at
        if rx_started is not None and rx_started.tzinfo is not None:
            rx_started = rx_started.astimezone(timezone.utc).replace(tzinfo=None)
        rx_ended = rx.ended_at
        if rx_ended is not None and rx_ended.tzinfo is not None:
            rx_ended = rx_ended.astimezone(timezone.utc).replace(tzinfo=None)

        if rx_started is not None and day_end <= rx_started:
            continue
        if rx_ended is not None and day_start >= rx_ended:
            continue

        slots = expand_schedule_for_day(rx.schedule, target_day)
        if not slots:
            continue
        existing = (
            session.query(Reminder)
            .filter(
                Reminder.prescription_id == rx.id,
                Reminder.scheduled_at >= day_start,
                Reminder.scheduled_at < day_end,
            )
            .all()
        )
        existing_times = {r.scheduled_at for r in existing}
        for slot in slots:
            if slot in existing_times:
                continue
            r = Reminder(
                prescription_id=rx.id,
                scheduled_at=slot,
                taken_at=None,
                skipped=False,
            )
            session.add(r)
        session.flush()

    session.commit()

    rxs_ids = [rx.id for rx in rxs]
    if not rxs_ids:
        return []
    reminders = (
        session.query(Reminder)
        .filter(
            Reminder.prescription_id.in_(rxs_ids),
            Reminder.scheduled_at >= day_start,
            Reminder.scheduled_at < day_end,
        )
        .order_by(Reminder.scheduled_at.asc())
        .all()
    )
    return reminders


def _serialize_reminder(r: Reminder, rx: Prescription) -> dict:
    return {
        "id": r.id,
        "prescription_id": r.prescription_id,
        "drug": {
            "id": rx.drug.id,
            "name": rx.drug.name,
            "generic_name": rx.drug.generic_name,
        },
        "dosage_mg": rx.dosage_mg,
        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
        "taken_at": r.taken_at.isoformat() if r.taken_at else None,
        "skipped": r.skipped,
    }


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@bp.get("")
def list_reminders():
    date_arg = request.args.get("date")
    today = (
        _parse_date(date_arg)
        if date_arg
        else datetime.now(timezone.utc).date()
    )
    if today is None:
        return _err("Invalid date.", "VALIDATION", 422)

    session = get_session()
    reminders = _ensure_reminders_for_day(session, today)

    blocks: dict[str, list[dict]] = {
        "morning": [],
        "midday": [],
        "evening": [],
        "night": [],
    }
    taken = 0
    skipped = 0
    pending = 0
    for r in reminders:
        rx = r.prescription
        blocks[_block_of(r.scheduled_at)].append(_serialize_reminder(r, rx))
        if r.taken_at is not None:
            taken += 1
        elif r.skipped:
            skipped += 1
        else:
            pending += 1

    return jsonify(
        {
            "date": today.isoformat(),
            "blocks": blocks,
            "totals": {"taken": taken, "skipped": skipped, "pending": pending},
        }
    )


def _own_reminder(session, rid: int) -> Reminder | None:
    r = session.get(Reminder, rid)
    if r is None:
        return None
    rx = r.prescription
    if rx is None or rx.patient_id != PATIENT_ID:
        return None
    return r


@bp.post("/<int:rid>/taken")
def mark_taken(rid: int):
    session = get_session()
    r = _own_reminder(session, rid)
    if r is None:
        return _err("Reminder not found.", "NOT_FOUND", 404)
    r.taken_at = datetime.now(timezone.utc).replace(tzinfo=None)
    r.skipped = False
    session.commit()
    session.refresh(r)
    return jsonify(_serialize_reminder(r, r.prescription))


@bp.post("/<int:rid>/skip")
def mark_skipped(rid: int):
    session = get_session()
    r = _own_reminder(session, rid)
    if r is None:
        return _err("Reminder not found.", "NOT_FOUND", 404)
    r.skipped = True
    r.taken_at = None
    session.commit()
    session.refresh(r)
    return jsonify(_serialize_reminder(r, r.prescription))
