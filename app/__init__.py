"""Flask app factory for MedSafety."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.exceptions import HTTPException

from .models import Base


log = logging.getLogger(__name__)


# Single-tenant: this app is for one household. We pin all data to one
# patient row, which the seed step creates on first boot.
PATIENT_ID = 1


def _load_dotenv() -> None:
    """Best-effort .env loader. Optional; if python-dotenv is missing we skip."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
    except Exception:
        pass


def _resolve_db_path() -> str:
    raw = os.environ.get("DB_PATH")
    if raw:
        return raw
    here = Path(__file__).resolve().parent.parent
    return str(here / "data" / "medsafety.db")


def _make_engine(db_path: str):
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{db_path}"
    engine = create_engine(
        url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    return engine


def _error_json(message: str, code: str, status: int):
    response = jsonify({"error": message, "code": code})
    response.status_code = status
    return response


def create_app() -> Flask:
    _load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    static_dir = str(Path(__file__).resolve().parent.parent / "static")
    app = Flask(__name__, static_folder=static_dir, static_url_path="")

    db_path = _resolve_db_path()
    engine = _make_engine(db_path)
    SessionLocal = scoped_session(
        sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    )
    app.extensions["db_engine"] = engine
    app.extensions["db_session"] = SessionLocal

    Base.metadata.create_all(engine)

    try:
        from . import seed as seed_mod

        with SessionLocal() as session:
            seed_mod.run_seed(session)
    except Exception:
        log.exception("Seed failed (continuing).")

    @app.teardown_appcontext
    def _remove_session(_exc):
        SessionLocal.remove()

    from .drugs import bp as drugs_bp
    from .prescriptions import bp as rx_bp
    from .interactions import bp as int_bp
    from .reminders import bp as rem_bp
    from .adherence import bp as adh_bp
    from .health import bp as health_bp

    app.register_blueprint(drugs_bp)
    app.register_blueprint(rx_bp)
    app.register_blueprint(int_bp)
    app.register_blueprint(rem_bp)
    app.register_blueprint(adh_bp)
    app.register_blueprint(health_bp)

    @app.route("/")
    def _root():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:filename>")
    def _static_passthrough(filename: str):
        target = Path(app.static_folder) / filename
        if target.is_file():
            return send_from_directory(app.static_folder, filename)
        if filename.startswith("api/"):
            return _error_json("Not found.", "NOT_FOUND", 404)
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        code_map = {
            400: "VALIDATION",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION",
            500: "SERVER",
        }
        code = code_map.get(err.code or 500, "SERVER")
        msg = err.description or "Error."
        return _error_json(msg, code, err.code or 500)

    @app.errorhandler(Exception)
    def _server_error(err: Exception):
        log.exception("Unhandled error: %s", err)
        return _error_json("Internal server error.", "SERVER", 500)

    return app


def get_session():
    """Return a fresh SQLAlchemy session from the current Flask app's scoped factory."""
    from flask import current_app

    return current_app.extensions["db_session"]()
