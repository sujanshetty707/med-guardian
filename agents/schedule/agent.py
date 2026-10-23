import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uagents import Agent, Context, Protocol
from core.config import settings
from core.models import (
    SaveMedicationsRequest, SaveMedicationsResponse,
    LogDoseRequest, LogDoseResponse,
    RunwayCheckRequest, RunwayCheckResponse, RunwayItem,
    AdherenceReportRequest, AdherenceReportResponse,
    MissedDoseEvent, CaregiverAlertResponse
)
from core.db import SessionLocal, Patient, Medication, Schedule, DoseEvent, AuditLog

logger = logging.getLogger("med-guardian.agents.schedule")

use_mailbox = bool(settings.AGENTVERSE_API_KEY)
schedule_agent = Agent(
    name="med-guardian-schedule",
    seed=settings.SCHEDULE_SEED,
    port=settings.SCHEDULE_PORT,
    mailbox=use_mailbox,
    agentverse=settings.AGENTVERSE_API_KEY if use_mailbox else None,
    endpoint=None if use_mailbox else [f"http://127.0.0.1:{settings.SCHEDULE_PORT}/submit"],
    publish_agent_details=True,
)

schedule_proto = Protocol(name="ScheduleProtocol", version="0.1.0")

@schedule_proto.on_message(model=SaveMedicationsRequest, replies=SaveMedicationsResponse)
async def handle_save_meds(ctx: Context, sender: str, msg: SaveMedicationsRequest):
    ctx.logger.info(f"Saving {len(msg.medications)} medications for patient {msg.patient_id} (session {msg.session_id})")
    
    with SessionLocal() as db:
        patient = db.query(Patient).filter(Patient.id == msg.patient_id).first()
        if not patient:
            patient = Patient(id=msg.patient_id, display_name="Dad (Ramesh)")
            db.add(patient)
            db.commit()

        saved_count = 0
        now = datetime.now(timezone.utc)

        for item in msg.medications:
            # Check if medication already exists
            med = db.query(Medication).filter(
                Medication.patient_id == msg.patient_id,
                Medication.display_name == item.drug_name
            ).first()

            if not med:
                med = Medication(
                    id=str(uuid.uuid4()),
                    patient_id=msg.patient_id,
                    rxcui=item.rxcui,
                    display_name=item.drug_name,
                    strength=item.strength,
                    instructions=item.instructions,
                    qty_on_hand=item.qty_on_hand,
                    qty_per_dose=item.qty_per_dose,
                    active=True
                )
                db.add(med)
                db.flush()

                sched = Schedule(
                    id=str(uuid.uuid4()),
                    medication_id=med.id,
                    times=json.dumps(item.times),
                    days=json.dumps([item.frequency])
                )
                db.add(sched)

                # Create an initial demo dose event
                due_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if due_time > now:
                    due_time = due_time - timedelta(days=1)
                
                dose = DoseEvent(
                    id=str(uuid.uuid4()),
                    medication_id=med.id,
                    due_at=due_time,
                    status="pending",
                    attempts=1
                )
                db.add(dose)
                saved_count += 1
            else:
                med.qty_on_hand = item.qty_on_hand
                med.strength = item.strength or med.strength
                saved_count += 1

        db.commit()

    await ctx.send(sender, SaveMedicationsResponse(
        session_id=msg.session_id,
        success=True,
        saved_count=saved_count,
        message=f"Successfully scheduled {saved_count} medications with reminder schedules."
    ))

@schedule_proto.on_message(model=LogDoseRequest, replies=LogDoseResponse)
async def handle_log_dose(ctx: Context, sender: str, msg: LogDoseRequest):
    ctx.logger.info(f"Logging dose action '{msg.action}' for '{msg.medication_name}'")
    
    with SessionLocal() as db:
        # Find medication
        med = db.query(Medication).filter(
            Medication.patient_id == msg.patient_id
        ).first()

        now = datetime.now(timezone.utc)
        if med:
            event = db.query(DoseEvent).filter(
                DoseEvent.medication_id == med.id
            ).order_by(DoseEvent.due_at.desc()).first()

            if not event:
                event = DoseEvent(
                    id=str(uuid.uuid4()),
                    medication_id=med.id,
                    due_at=now,
                    status=msg.action,
                    confirmed_at=now,
                    source=msg.channel
                )
                db.add(event)
            else:
                event.status = msg.action
                event.confirmed_at = now
                event.source = msg.channel

            if msg.action == "taken" and med.qty_on_hand > 0:
                med.qty_on_hand -= med.qty_per_dose

            db.commit()

    await ctx.send(sender, LogDoseResponse(
        session_id=msg.session_id,
        success=True,
        message=f"Recorded dose as '{msg.action.upper()}'."
    ))

@schedule_proto.on_message(model=RunwayCheckRequest, replies=RunwayCheckResponse)
async def handle_runway_check(ctx: Context, sender: str, msg: RunwayCheckRequest):
    ctx.logger.info(f"Calculating refill runways for patient {msg.patient_id}")
    items: List[RunwayItem] = []

    with SessionLocal() as db:
        meds = db.query(Medication).filter(
            Medication.patient_id == msg.patient_id,
            Medication.active == True
        ).all()

        for m in meds:
            doses_per_day = 1
            if m.schedules:
                times_list = json.loads(m.schedules[0].times or "[]")
                doses_per_day = max(1, len(times_list))
            
            days_left = int(m.qty_on_hand / (m.qty_per_dose * doses_per_day))
            needs_refill = days_left <= settings.REFILL_THRESHOLD_DAYS
            
            items.append(RunwayItem(
                medication_id=m.id,
                medication_name=m.display_name,
                rxcui=m.rxcui or "",
                strength=m.strength,
                qty_on_hand=m.qty_on_hand,
                days_left=days_left,
                needs_refill=needs_refill
            ))

    await ctx.send(sender, RunwayCheckResponse(
        session_id=msg.session_id,
        items=items
    ))

@schedule_proto.on_message(model=AdherenceReportRequest, replies=AdherenceReportResponse)
async def handle_adherence_report(ctx: Context, sender: str, msg: AdherenceReportRequest):
    ctx.logger.info(f"Generating {msg.days}-day adherence report for patient {msg.patient_id}")
    
    with SessionLocal() as db:
        patient = db.query(Patient).filter(Patient.id == msg.patient_id).first()
        patient_name = patient.display_name if patient else "Dad"
        
        events = db.query(DoseEvent).join(Medication).filter(
            Medication.patient_id == msg.patient_id
        ).all()

        taken = sum(1 for e in events if e.status == "taken")
        skipped = sum(1 for e in events if e.status == "skipped")
        missed = sum(1 for e in events if e.status in ["missed", "pending"])
        total = max(1, taken + skipped + missed)

        rate = round((taken / total) * 100.0, 1)
        summary = (
            f"Adherence score: {rate}%. "
            f"({taken} doses taken, {skipped} skipped, {missed} unconfirmed over the past {msg.days} days)."
        )

    await ctx.send(sender, AdherenceReportResponse(
        session_id=msg.session_id,
        patient_name=patient_name,
        adherence_rate=rate,
        taken_count=taken,
        skipped_count=skipped,
        missed_count=missed,
        summary=summary
    ))

schedule_agent.include(schedule_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Starting Schedule Agent on port {settings.SCHEDULE_PORT} (address: {schedule_agent.address})")
    schedule_agent.run()
