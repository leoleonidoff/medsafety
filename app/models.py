"""SQLAlchemy 2 declarative ORM for MedSafety."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    try:
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    except Exception:
        pass


class Patient(Base):
    """The single patient this instance belongs to. One row, fixed id=1."""

    __tablename__ = "patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=_utcnow
    )

    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rxnorm_cui: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    drug_class: Mapped[str] = mapped_column(String(128), nullable=False)


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient.id", ondelete="CASCADE"), nullable=False
    )
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id", ondelete="RESTRICT"), nullable=False
    )
    dosage_mg: Mapped[float] = mapped_column(Float, nullable=False)
    schedule: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="prescriptions")
    drug: Mapped["Drug"] = relationship()

    __table_args__ = (
        Index("ix_prescription_patient_active", "patient_id", "active"),
    )


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drug_a_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False
    )
    drug_b_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    llm_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    drug_a: Mapped["Drug"] = relationship(foreign_keys=[drug_a_id])
    drug_b: Mapped["Drug"] = relationship(foreign_keys=[drug_b_id])

    __table_args__ = (
        UniqueConstraint("drug_a_id", "drug_b_id", name="uq_interaction_pair"),
        CheckConstraint(
            "severity in ('contraindicated','major','moderate','minor')",
            name="ck_interaction_severity",
        ),
        CheckConstraint("drug_a_id < drug_b_id", name="ck_interaction_pair_order"),
        Index("ix_interaction_pair", "drug_a_id", "drug_b_id"),
    )


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    taken_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=_utcnow
    )

    prescription: Mapped["Prescription"] = relationship()

    __table_args__ = (
        Index(
            "ix_reminder_prescription_scheduled",
            "prescription_id",
            "scheduled_at",
        ),
    )


def pair_ids(a: int, b: int) -> tuple[int, int]:
    """Normalize a drug pair so the lower id is first."""
    if a == b:
        raise ValueError("pair_ids: a == b")
    return (a, b) if a < b else (b, a)
