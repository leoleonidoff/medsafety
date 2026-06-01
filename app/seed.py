"""First-boot seeding: drugs, interactions, demo prescriptions and reminders."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from . import PATIENT_ID
from .interactions_db import DRUGS, build_pairs
from .models import Drug, Interaction, Patient, Prescription, Reminder, pair_ids
from .reminders import expand_schedule_for_day


log = logging.getLogger(__name__)


def _seed_drugs(session) -> dict[str, Drug]:
    existing = {d.generic_name: d for d in session.query(Drug).all()}
    if existing:
        return existing
    out: dict[str, Drug] = {}
    for name, generic, drug_class, cui in DRUGS:
        d = Drug(
            rxnorm_cui=cui,
            name=name,
            generic_name=generic,
            drug_class=drug_class,
        )
        session.add(d)
        out[generic] = d
    session.flush()
    return out


def _seed_interactions(session, drugs_by_generic: dict[str, Drug]) -> None:
    if session.query(Interaction).count() > 0:
        return
    pairs = build_pairs()
    inserted = 0
    skipped = 0
    for gen_a, gen_b, severity, mechanism in pairs:
        a = drugs_by_generic.get(gen_a)
        b = drugs_by_generic.get(gen_b)
        if a is None or b is None:
            skipped += 1
            continue
        low, high = pair_ids(a.id, b.id)
        existing = (
            session.query(Interaction)
            .filter(Interaction.drug_a_id == low, Interaction.drug_b_id == high)
            .one_or_none()
        )
        if existing is not None:
            continue
        session.add(
            Interaction(
                drug_a_id=low,
                drug_b_id=high,
                severity=severity,
                mechanism=mechanism,
            )
        )
        inserted += 1
    session.flush()
    log.info("Seeded %d interactions (%d skipped)", inserted, skipped)


def _seed_patient(session) -> Patient:
    existing = session.get(Patient, PATIENT_ID)
    if existing is not None:
        return existing
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    patient = Patient(
        id=PATIENT_ID,
        display_name="Demo Patient",
        created_at=now,
    )
    session.add(patient)
    session.flush()
    return patient


def _seed_demo_prescriptions(session, patient: Patient, drugs_by_generic: dict[str, Drug]) -> None:
    if session.query(Prescription).filter(Prescription.patient_id == patient.id).count() > 0:
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def _rx(generic: str, dosage_mg: float, schedule: str, days_ago: int) -> Prescription:
        drug = drugs_by_generic[generic]
        started = now - timedelta(days=days_ago)
        rx = Prescription(
            patient_id=patient.id,
            drug_id=drug.id,
            dosage_mg=dosage_mg,
            schedule=schedule,
            started_at=started,
            ended_at=None,
            active=True,
            notes=None,
        )
        session.add(rx)
        return rx

    rxs: list[Prescription] = [
        _rx("warfarin", 5, "evening", 90),
        _rx("ibuprofen", 400, "every 8h", 14),
        _rx("lisinopril", 10, "morning", 365),
        _rx("atorvastatin", 20, "evening", 200),
        _rx("clarithromycin", 500, "every 12h", 5),
        _rx("omeprazole", 20, "morning", 60),
    ]
    session.flush()

    _seed_demo_reminders(session, rxs, now)
    session.flush()


def _seed_demo_reminders(session, rxs: list[Prescription], now: datetime) -> None:
    import random

    today = now.date()
    rng = random.Random(20260515)

    skip_days = {6, 4, 3, 1}

    for rx in rxs:
        for days_ago in range(7, 0, -1):
            target_day = today - timedelta(days=days_ago)
            if rx.started_at and target_day < rx.started_at.date():
                continue
            slots = expand_schedule_for_day(rx.schedule, target_day)
            for slot in slots:
                existing = (
                    session.query(Reminder)
                    .filter(
                        Reminder.prescription_id == rx.id,
                        Reminder.scheduled_at == slot,
                    )
                    .one_or_none()
                )
                if existing is not None:
                    continue
                if days_ago in skip_days and rng.random() < 0.06:
                    r = Reminder(
                        prescription_id=rx.id,
                        scheduled_at=slot,
                        taken_at=None,
                        skipped=True,
                    )
                else:
                    jitter_min = rng.randint(-8, 8)
                    taken_at = slot + timedelta(minutes=jitter_min)
                    r = Reminder(
                        prescription_id=rx.id,
                        scheduled_at=slot,
                        taken_at=taken_at,
                        skipped=False,
                    )
                session.add(r)


def run_seed(session) -> None:
    """Idempotent seed. Creates the single patient row + demo data on first boot."""
    drugs = _seed_drugs(session)
    _seed_interactions(session, drugs)
    patient = _seed_patient(session)
    _seed_demo_prescriptions(session, patient, drugs)
    session.commit()
