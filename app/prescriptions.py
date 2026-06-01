"""/api/me/prescriptions/* endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from . import PATIENT_ID, get_session
from .models import Drug, Prescription
from .rxnorm import fetch_generic_name
from .schemas import PrescriptionIn, PrescriptionPatch


bp = Blueprint("prescriptions", __name__, url_prefix="/api/me/prescriptions")


def _err(msg: str, code: str, status: int):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    return resp


def _serialize(rx: Prescription) -> dict:
    return {
        "id": rx.id,
        "drug": {
            "id": rx.drug.id,
            "name": rx.drug.name,
            "generic_name": rx.drug.generic_name,
            "drug_class": rx.drug.drug_class,
        },
        "dosage_mg": rx.dosage_mg,
        "schedule": rx.schedule,
        "started_at": rx.started_at.isoformat() if rx.started_at else None,
        "ended_at": rx.ended_at.isoformat() if rx.ended_at else None,
        "active": rx.active,
        "notes": rx.notes,
    }


def _upsert_drug_by_cui(session, cui: str) -> Optional[Drug]:
    cui = (cui or "").strip()
    if not cui:
        return None
    existing = session.query(Drug).filter(Drug.rxnorm_cui == cui).one_or_none()
    if existing is not None:
        return existing
    generic = fetch_generic_name(cui)
    if generic is None:
        return None
    generic_name, _ = generic
    drug = Drug(
        rxnorm_cui=cui,
        name=generic_name,
        generic_name=generic_name,
        drug_class="unknown",
    )
    session.add(drug)
    session.flush()
    return drug


@bp.get("")
def list_prescriptions():
    session = get_session()
    q = session.query(Prescription).filter(Prescription.patient_id == PATIENT_ID)
    active_arg = request.args.get("active")
    if active_arg is not None:
        if active_arg.lower() in ("1", "true", "yes"):
            q = q.filter(Prescription.active.is_(True))
        elif active_arg.lower() in ("0", "false", "no"):
            q = q.filter(Prescription.active.is_(False))
    rows = q.order_by(Prescription.started_at.desc()).all()
    return jsonify([_serialize(r) for r in rows])


@bp.post("")
def create_prescription():
    data = request.get_json(silent=True) or {}
    try:
        body = PrescriptionIn(**data)
    except ValidationError as e:
        return _err(str(e.errors()[0].get("msg", "Invalid input.")), "VALIDATION", 422)

    if body.drug_id is None and not body.rxnorm_cui:
        return _err("Either drug_id or rxnorm_cui is required.", "VALIDATION", 422)

    session = get_session()
    drug: Optional[Drug] = None
    if body.drug_id is not None:
        drug = session.get(Drug, body.drug_id)
        if drug is None:
            return _err("Drug not found.", "NOT_FOUND", 404)
    else:
        drug = _upsert_drug_by_cui(session, body.rxnorm_cui or "")
        if drug is None:
            return _err(
                "Could not resolve drug from RxNorm CUI.",
                "RXNORM_UNAVAILABLE",
                503,
            )

    started_at = body.started_at or datetime.now(timezone.utc).replace(tzinfo=None)
    if started_at.tzinfo is not None:
        started_at = started_at.astimezone(timezone.utc).replace(tzinfo=None)

    rx = Prescription(
        patient_id=PATIENT_ID,
        drug_id=drug.id,
        dosage_mg=body.dosage_mg,
        schedule=body.schedule.strip(),
        started_at=started_at,
        ended_at=None,
        active=True,
        notes=body.notes,
    )
    session.add(rx)
    session.commit()
    session.refresh(rx)
    return jsonify(_serialize(rx)), 201


@bp.patch("/<int:rx_id>")
def patch_prescription(rx_id: int):
    data = request.get_json(silent=True) or {}
    try:
        body = PrescriptionPatch(**data)
    except ValidationError as e:
        return _err(str(e.errors()[0].get("msg", "Invalid input.")), "VALIDATION", 422)

    session = get_session()
    rx = session.get(Prescription, rx_id)
    if rx is None or rx.patient_id != PATIENT_ID:
        return _err("Prescription not found.", "NOT_FOUND", 404)

    if body.dosage_mg is not None:
        rx.dosage_mg = body.dosage_mg
    if body.schedule is not None:
        rx.schedule = body.schedule.strip()
    if body.notes is not None:
        rx.notes = body.notes
    if body.active is not None:
        rx.active = bool(body.active)
        if not body.active and rx.ended_at is None:
            rx.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if body.active:
            rx.ended_at = None

    session.commit()
    session.refresh(rx)
    return jsonify(_serialize(rx))


@bp.delete("/<int:rx_id>")
def delete_prescription(rx_id: int):
    session = get_session()
    rx = session.get(Prescription, rx_id)
    if rx is None or rx.patient_id != PATIENT_ID:
        return _err("Prescription not found.", "NOT_FOUND", 404)
    rx.active = False
    rx.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.commit()
    return jsonify({"ok": True})
