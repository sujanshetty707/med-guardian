import logging
import uuid
from datetime import datetime, timezone
from uagents import Agent, Context, Protocol
from core.config import settings
from core.models import (
    MissedDoseEvent, CaregiverAlertResponse,
    LinkCaregiverRequest, LinkCaregiverResponse
)
from core.db import SessionLocal, CaregiverLink, Patient, User
from tools.notify.dispatcher import dispatcher

logger = logging.getLogger("med-guardian.agents.caregiver")

caregiver_agent = Agent(
    name="med-guardian-caregiver",
    seed=settings.CAREGIVER_SEED,
    port=settings.CAREGIVER_PORT,
    endpoint=[f"http://127.0.0.1:{settings.CAREGIVER_PORT}/submit"],
)

caregiver_proto = Protocol(name="CaregiverProtocol", version="0.1.0")

@caregiver_proto.on_message(model=MissedDoseEvent, replies=CaregiverAlertResponse)
async def handle_missed_dose_escalation(ctx: Context, sender: str, msg: MissedDoseEvent):
    ctx.logger.warning(
        f"ESCALATION: Patient {msg.patient_name} missed {msg.med_name} {msg.strength} due at {msg.due_at_iso} after {msg.attempts} attempts."
    )
    event_id = f"evt_{uuid.uuid4().hex[:8]}"

    # Look up registered caregiver in database
    caregiver_name = "Family Caregiver"
    caregiver_contact = settings.TELEGRAM_DEFAULT_CHAT_ID
    channel = msg.caregiver_channel

    with SessionLocal() as db:
        link = db.query(CaregiverLink).filter(
            CaregiverLink.patient_id == msg.patient_id,
            CaregiverLink.revoked_at == None
        ).first()
        if link:
            caregiver_name = link.caregiver_name
            caregiver_contact = link.caregiver_contact or caregiver_contact
            channel = link.channel

    # Dispatch notification to caregiver
    dispatched = await dispatcher.dispatch_caregiver_alert(
        caregiver_name=caregiver_name,
        patient_name=msg.patient_name,
        medication_name=msg.med_name,
        strength=msg.strength,
        due_time=msg.due_at_iso,
        channel=channel,
        channel_addr=caregiver_contact
    )

    await ctx.send(sender, CaregiverAlertResponse(
        event_id=event_id,
        dispatched=dispatched,
        channel=channel,
        message=f"Escalation alert successfully sent to {caregiver_name} via {channel}."
    ))

@caregiver_proto.on_message(model=LinkCaregiverRequest, replies=LinkCaregiverResponse)
async def handle_link_caregiver(ctx: Context, sender: str, msg: LinkCaregiverRequest):
    ctx.logger.info(f"Linking caregiver {msg.caregiver_name} to patient {msg.patient_id}")
    link_id = f"lnk_{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        # Check patient exists
        patient = db.query(Patient).filter(Patient.id == msg.patient_id).first()
        if not patient:
            # Create demo patient record if needed
            patient = Patient(id=msg.patient_id, display_name="Ramesh (Dad)")
            db.add(patient)
            db.commit()

        link = CaregiverLink(
            id=link_id,
            patient_id=msg.patient_id,
            caregiver_name=msg.caregiver_name,
            caregiver_contact=msg.contact_info,
            channel=msg.channel,
            consent_at=datetime.now(timezone.utc)
        )
        db.add(link)
        db.commit()

    await ctx.send(sender, LinkCaregiverResponse(
        session_id=msg.session_id,
        success=True,
        link_id=link_id,
        message=f"Caregiver {msg.caregiver_name} successfully linked with patient consent recorded."
    ))

caregiver_agent.include(caregiver_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Starting Caregiver Agent on port {settings.CAREGIVER_PORT} (address: {caregiver_agent.address})")
    caregiver_agent.run()
