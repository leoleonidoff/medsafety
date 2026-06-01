"""/api/health endpoint."""
from __future__ import annotations

import os
from flask import Blueprint, jsonify

from . import get_session
from .ai import next_engine
from .models import Drug, Interaction


bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    session = get_session()
    drug_count = session.query(Drug).count()
    interaction_count = session.query(Interaction).count()
    rx_base = os.environ.get("RXNORM_BASE_URL", "")
    rxnorm = "live" if rx_base else "local"
    return jsonify(
        {
            "ok": True,
            "ai": next_engine(),
            "rxnorm": rxnorm,
            "drug_count": drug_count,
            "interaction_count": interaction_count,
        }
    )
