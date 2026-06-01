"""/api/me/interactions endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from . import PATIENT_ID, get_session
from .ai import explain_interaction
from .models import Drug, Interaction, Prescription


bp = Blueprint("interactions", __name__, url_prefix="/api/me/interactions")


SEVERITY_ORDER = ["contraindicated", "major", "moderate", "minor"]


def _err(msg: str, code: str, status: int):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    return resp


def _active_drug_ids(session) -> list[int]:
    rows = (
        session.query(Prescription.drug_id)
        .filter(Prescription.patient_id == PATIENT_ID, Prescription.active.is_(True))
        .all()
    )
    return [r[0] for r in rows]


@bp.get("")
def list_interactions():
    session = get_session()
    drug_ids = _active_drug_ids(session)

    counts = {k: 0 for k in SEVERITY_ORDER}
    groups: dict[str, list[dict]] = {k: [] for k in SEVERITY_ORDER}

    if len(drug_ids) < 2:
        return jsonify({"counts": counts, "groups": groups})

    rows = (
        session.query(Interaction)
        .filter(
            Interaction.drug_a_id.in_(drug_ids),
            Interaction.drug_b_id.in_(drug_ids),
        )
        .all()
    )

    drug_map: dict[int, Drug] = {}
    needed_ids = {r.drug_a_id for r in rows} | {r.drug_b_id for r in rows}
    if needed_ids:
        for d in session.query(Drug).filter(Drug.id.in_(needed_ids)).all():
            drug_map[d.id] = d

    for r in rows:
        a = drug_map.get(r.drug_a_id)
        b = drug_map.get(r.drug_b_id)
        if a is None or b is None:
            continue
        sev = r.severity if r.severity in groups else "minor"
        groups[sev].append(
            {
                "interaction_id": r.id,
                "drug_a": {"id": a.id, "name": a.name},
                "drug_b": {"id": b.id, "name": b.name},
                "severity": r.severity,
                "mechanism": r.mechanism,
                "has_explanation": bool(r.llm_explanation),
            }
        )
        counts[sev] += 1

    for sev in groups:
        groups[sev].sort(key=lambda it: (it["drug_a"]["name"].lower(), it["drug_b"]["name"].lower()))

    return jsonify({"counts": counts, "groups": groups})


@bp.post("/<int:interaction_id>/explain")
def explain(interaction_id: int):
    refresh = (request.args.get("refresh", "").lower() in ("1", "true", "yes"))

    session = get_session()
    inter = session.get(Interaction, interaction_id)
    if inter is None:
        return _err("Interaction not found.", "NOT_FOUND", 404)

    active_ids = set(_active_drug_ids(session))
    if inter.drug_a_id not in active_ids or inter.drug_b_id not in active_ids:
        return _err("Interaction not in your active list.", "FORBIDDEN", 403)

    if inter.llm_explanation and not refresh:
        return jsonify(
            {
                "interaction_id": inter.id,
                "explanation": inter.llm_explanation,
                "model": inter.llm_model or "template",
                "cached": True,
            }
        )

    drug_a = session.get(Drug, inter.drug_a_id)
    drug_b = session.get(Drug, inter.drug_b_id)
    if drug_a is None or drug_b is None:
        return _err("Drug data missing.", "SERVER", 500)

    text, model = explain_interaction(
        drug_a.name,
        drug_a.drug_class,
        drug_b.name,
        drug_b.drug_class,
        inter.severity,
        inter.mechanism,
    )

    inter.llm_explanation = text
    inter.llm_model = model
    session.commit()

    return jsonify(
        {
            "interaction_id": inter.id,
            "explanation": text,
            "model": model,
            "cached": False,
        }
    )
