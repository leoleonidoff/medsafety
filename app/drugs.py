"""/api/drugs/* endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from . import get_session
from .ai import answer_drug_question
from .models import Drug
from .rxnorm import search_drugs


bp = Blueprint("drugs", __name__, url_prefix="/api/drugs")


def _err(msg: str, code: str, status: int):
    resp = jsonify({"error": msg, "code": code})
    resp.status_code = status
    return resp


@bp.get("/search")
def search():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return _err("Query must be at least 2 characters.", "VALIDATION", 422)
    session = get_session()
    payload = search_drugs(session, q)
    return jsonify(payload)


@bp.get("/<int:drug_id>")
def get_drug(drug_id: int):
    session = get_session()
    drug = session.get(Drug, drug_id)
    if drug is None:
        return _err("Drug not found.", "NOT_FOUND", 404)
    return jsonify(
        {
            "id": drug.id,
            "rxnorm_cui": drug.rxnorm_cui,
            "name": drug.name,
            "generic_name": drug.generic_name,
            "drug_class": drug.drug_class,
        }
    )


@bp.post("/<int:drug_id>/ask")
def ask_drug(drug_id: int):
    session = get_session()
    drug = session.get(Drug, drug_id)
    if drug is None:
        return _err("Drug not found.", "NOT_FOUND", 404)
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if len(question) < 3:
        return _err("Question must be at least 3 characters.", "VALIDATION", 422)
    if len(question) > 240:
        return _err("Question must be 240 characters or fewer.", "VALIDATION", 422)

    answer, model = answer_drug_question(
        drug_name=drug.name,
        drug_class=drug.drug_class or "unknown",
        generic_name=drug.generic_name or drug.name,
        question=question,
    )
    return jsonify({
        "drug_id": drug.id,
        "drug_name": drug.name,
        "question": question,
        "answer": answer,
        "llm_model": model,
    })
