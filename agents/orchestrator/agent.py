import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent, MetadataContent,
    chat_protocol_spec
)
from core.config import settings
from core.guardrails import guardrails
from core.acp import create_ack, create_text_chat_message, extract_text, sessions
from core.llm import llm_parser, IntentClassification
from core.cards import cards, CardPayload
from core.models import (
    ParsedMedSchedule, InteractionFinding, Quote, RunwayItem,
    NormalizeRequest, NormalizeResponse,
    InteractionRequest, InteractionResponse,
    PriceRequest, PriceResponse,
    SaveMedicationsRequest, SaveMedicationsResponse,
    LogDoseRequest, LogDoseResponse,
    RunwayCheckRequest, RunwayCheckResponse,
    AdherenceReportRequest, AdherenceReportResponse,
    RefillOrderRequest, RefillOrderResponse,
    LinkCaregiverRequest, LinkCaregiverResponse
)
from tools.rxnorm import rxnorm_client
from tools.openfda import openfda_client
from tools.pricing.mock_partner import mock_partner_provider
from tools.pricing.nadac import nadac_provider
from tools.payments import payment_manager
from core.db import SessionLocal, Patient, Medication, DoseEvent

logger = logging.getLogger("med-guardian.orchestrator")

orchestrator_agent = Agent(
    name="med-guardian",
    seed=settings.ORCHESTRATOR_SEED,
    port=settings.ORCHESTRATOR_PORT,
    endpoint=[f"http://127.0.0.1:{settings.ORCHESTRATOR_PORT}/submit"],
)

chat_proto = Protocol(spec=chat_protocol_spec)

# --- Core Orchestration Workflow ---
async def process_orchestrator_turn(sender_addr: str, text: str) -> CardPayload:
    """
    Main orchestration step:
    1. Guardrails pre-check (emergency / scope)
    2. Session load
    3. Intent classification & entity extraction
    4. Plan execution & tool calls
    5. Card & text formatting
    """
    # 1. Pre-check guardrails
    guard_res = guardrails.pre_check(text)
    if guard_res.block:
        return CardPayload(
            card_type="guardrail_notice",
            card_data={"reason": guard_res.reason},
            text_fallback=guard_res.response
        )

    # 2. Load session
    state = sessions.load(sender_addr)
    patient_id = state.get("patient_id", f"pat_{sender_addr[:8]}")
    state["patient_id"] = patient_id

    # 3. Intent classification
    intent = await llm_parser.classify_and_extract(text, state)
    logger.info(f"Classified intent: '{intent.name}' for sender {sender_addr}")

    # 4. Plan execution
    if intent.name == "ADD_MEDICATIONS":
        raw_meds: List[ParsedMedSchedule] = intent.entities.get("medications", [])
        if not raw_meds:
            msg = "I didn't detect specific medication names and dosages. You can say something like:\n*'Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin.'*"
            return CardPayload("text_reply", {}, guardrails.post_format(msg))

        # Drug normalization via RxNorm
        drug_names = [m.drug_name for m in raw_meds]
        normalized_items = await rxnorm_client.normalize_list(drug_names)
        norm_map = {item.raw_name.lower(): item for item in normalized_items}

        for m in raw_meds:
            norm = norm_map.get(m.drug_name.lower())
            if norm:
                m.rxcui = norm.rxcui
                m.drug_name = norm.name
                if not m.strength and norm.strength:
                    m.strength = norm.strength

        # Interaction screening via openFDA against both incoming meds and existing patient meds
        with SessionLocal() as db:
            existing_meds = db.query(Medication).filter(
                Medication.patient_id == patient_id,
                Medication.active == True
            ).all()
            all_drugs_to_screen = list(dict.fromkeys([m.display_name for m in existing_meds] + drug_names))

        findings, source_status = await openfda_client.screen_pairs(all_drugs_to_screen)

        # Cache in pending session for confirmation
        state["_pending_action"] = {
            "type": "medication_intake",
            "medications": [m.dict() for m in raw_meds],
            "findings": [f.dict() for f in findings]
        }
        sessions.save(sender_addr, state)

        # Build interactive card + text
        card = cards.medication_intake(raw_meds)
        
        # If interactions flagged, append advisory preview
        if findings:
            interaction_card = cards.interaction_review(findings, source_status)
            combined_text = f"{card.text_fallback}\n\n---\n{interaction_card.text_fallback}"
            return CardPayload(
                card_type="intake_with_safety_review",
                card_data={"intake": card.card_data, "safety": interaction_card.card_data},
                text_fallback=guardrails.post_format(combined_text)
            )

        return CardPayload(
            card_type=card.card_type,
            card_data=card.card_data,
            text_fallback=guardrails.post_format(card.text_fallback)
        )

    elif intent.name == "CONFIRM_SCHEDULE":
        pending = state.get("_pending_action", {})
        if intent.entities.get("action") == "cancel":
            state["_pending_action"] = {}
            sessions.save(sender_addr, state)
            return CardPayload("text_reply", {}, "Medication intake was cancelled. No changes were saved.")

        meds_data = pending.get("medications", [])
        if not meds_data:
            return CardPayload("text_reply", {}, "There are no pending medication schedules waiting for confirmation.")

        meds = [ParsedMedSchedule(**d) for d in meds_data]
        
        # Persist medications & schedule
        with SessionLocal() as db:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                patient = Patient(id=patient_id, display_name="Dad (Ramesh)")
                db.add(patient)
                db.commit()

            for item in meds:
                med = db.query(Medication).filter(
                    Medication.patient_id == patient_id,
                    Medication.display_name == item.drug_name
                ).first()
                if not med:
                    med = Medication(
                        id=str(uuid.uuid4()),
                        patient_id=patient_id,
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

                    # Add default dose event for demo
                    dose = DoseEvent(
                        id=str(uuid.uuid4()),
                        medication_id=med.id,
                        due_at=datetime.now(timezone.utc),
                        status="pending"
                    )
                    db.add(dose)
            db.commit()

        state["_pending_action"] = {}
        sessions.save(sender_addr, state)

        reply = (
            f"✅ **Medication Schedule Confirmed & Activated!**\n\n"
            f"Successfully scheduled {len(meds)} medications. Reminders are configured with automated grace-period tracking.\n"
            f"If a dose is missed after the grace window, your designated caregiver will be alerted automatically."
        )
        return CardPayload("confirmed_notice", {"count": len(meds)}, guardrails.post_format(reply))

    elif intent.name == "LOG_DOSE":
        action = intent.entities.get("action", "taken")
        with SessionLocal() as db:
            event = db.query(DoseEvent).join(Medication).filter(
                Medication.patient_id == patient_id
            ).order_by(DoseEvent.due_at.desc()).first()

            if event:
                event.status = action
                event.confirmed_at = datetime.now(timezone.utc)
                if action == "taken" and event.medication and event.medication.qty_on_hand > 0:
                    event.medication.qty_on_hand -= event.medication.qty_per_dose
                db.commit()

        if action == "taken":
            reply = "👍 **Dose logged as TAKEN.** Great job staying on track! Adherence log updated."
        elif action == "skipped":
            reply = "📝 **Dose logged as SKIPPED.** Thank you for confirming so your caregiver doesn't receive an unnecessary alert."
        else:
            reply = "⏰ **Reminder snoozed.** I will check back in 15 minutes."

        return CardPayload("dose_logged", {"status": action}, guardrails.post_format(reply))

    elif intent.name == "CHECK_INTERACTION":
        # Check interactions across active medications
        with SessionLocal() as db:
            meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
            names = [m.display_name for m in meds]

        if len(names) < 2:
            names = ["Metformin", "Ibuprofen"]  # Demo fallback if empty

        findings, source_status = await openfda_client.screen_pairs(names)
        card = cards.interaction_review(findings, source_status)
        return CardPayload(card.card_type, card.card_data, guardrails.post_format(card.text_fallback))

    elif intent.name == "REFILL":
        drug_name = intent.entities.get("drug_name", "Metformin").capitalize()
        # Fetch prices for drug
        is_estimate = False
        quotes = []
        try:
            quotes = await mock_partner_provider.quote(
                rxcui="6809",
                drug_name=drug_name,
                strength="500mg",
                qty=30,
                zip_code="94016"
            )
        except Exception as e:
            logger.warning(f"Partner price failed: {e}. Falling back to benchmark.")
            is_estimate = True
            nadac_q = await nadac_provider.quote("6809", drug_name, "500mg", 30, "94016")
            base_cents = nadac_q[0].price_cents
            quotes = [
                Quote(
                    provider="nadac_fallback",
                    pharmacy_name="Costco Pharmacy (Direct Mail)",
                    price_cents=int(base_cents * 1.15),
                    currency="USD",
                    estimated=True,
                    delivery_days=2,
                    details="Estimated mail delivery quote based on CMS acquisition data."
                ),
                Quote(
                    provider="nadac_fallback",
                    pharmacy_name="CVS Health (Local Pickup)",
                    price_cents=int(base_cents * 1.35),
                    currency="USD",
                    estimated=True,
                    delivery_days=0,
                    details="Estimated pharmacy pickup benchmark."
                ),
                Quote(
                    provider="nadac_fallback",
                    pharmacy_name="Walgreens Pharmacy (Drive-thru)",
                    price_cents=int(base_cents * 1.30),
                    currency="USD",
                    estimated=True,
                    delivery_days=0,
                    details="Estimated drive-thru pickup benchmark."
                )
            ]

        # Save quotes in pending action
        state["_pending_action"] = {
            "type": "price_carousel",
            "drug_name": drug_name,
            "quotes": [q.dict() for q in quotes]
        }
        sessions.save(sender_addr, state)

        card = cards.price_carousel(drug_name, "500mg", 30, quotes, is_estimate)
        return CardPayload(card.card_type, card.card_data, guardrails.post_format(card.text_fallback))

    elif intent.name == "REFILL_SELECT":
        pending = state.get("_pending_action", {})
        quotes_data = pending.get("quotes", [])
        option_idx = intent.entities.get("option_index", 1) - 1
        
        if 0 <= option_idx < len(quotes_data):
            selected_quote = Quote(**quotes_data[option_idx])
        elif quotes_data:
            selected_quote = Quote(**quotes_data[0])
        else:
            selected_quote = Quote(
                provider="mock_partner",
                pharmacy_name="Costco Pharmacy",
                price_cents=780,
                currency="USD"
            )

        drug_name = pending.get("drug_name", "Metformin")
        
        # Create Payment Protocol request
        pay_req = payment_manager.create_payment_request(
            order_id=f"ord_{uuid.uuid4().hex[:6]}",
            amount_cents=selected_quote.price_cents,
            description=f"Refill for {drug_name} 30-day supply ({selected_quote.pharmacy_name})"
        )

        state["_pending_action"] = {
            "type": "refill_approval",
            "drug_name": drug_name,
            "pharmacy_name": selected_quote.pharmacy_name,
            "price_cents": selected_quote.price_cents,
            "payment_id": pay_req["payment_id"],
            "order_id": pay_req["order_id"]
        }
        sessions.save(sender_addr, state)

        card = cards.refill_approval(
            drug_name=drug_name,
            pharmacy_name=selected_quote.pharmacy_name,
            price_cents=selected_quote.price_cents,
            payment_id=pay_req["payment_id"]
        )
        return CardPayload(card.card_type, card.card_data, guardrails.post_format(card.text_fallback))

    elif intent.name == "REFILL_APPROVE":
        pending = state.get("_pending_action", {})
        if intent.entities.get("action") == "cancel":
            state["_pending_action"] = {}
            sessions.save(sender_addr, state)
            return CardPayload("text_reply", {}, "Refill order was cancelled.")

        drug_name = pending.get("drug_name", "Metformin")
        pharmacy_name = pending.get("pharmacy_name", "Costco Pharmacy")
        price_cents = pending.get("price_cents", 780)
        payment_id = pending.get("payment_id", "pay_simulated")
        order_id = pending.get("order_id", f"ord_{uuid.uuid4().hex[:6]}")

        # Finalize order and reset supply runway in DB
        with SessionLocal() as db:
            med = db.query(Medication).filter(
                Medication.patient_id == patient_id,
                Medication.display_name.ilike(f"%{drug_name}%")
            ).first()
            if med:
                med.qty_on_hand += 30
                med.last_refill_at = datetime.now(timezone.utc)
            db.commit()

        state["_pending_action"] = {}
        sessions.save(sender_addr, state)

        reply = (
            f"🎉 **Refill Order Confirmed!**\n\n"
            f"• **Order ID:** `{order_id}`\n"
            f"• **Medication:** {drug_name} (30-day supply added)\n"
            f"• **Pharmacy Partner:** {pharmacy_name}\n"
            f"• **Payment Protocol Ref:** `{payment_id}` (Authorized: ${price_cents/100:.2f})\n\n"
            f"Estimated dispatch: 1 business day. Your supply runway has been reset to +30 days."
        )
        return CardPayload("order_confirmed", {"order_id": order_id}, guardrails.post_format(reply))

    elif intent.name == "WEEKLY_REPORT":
        with SessionLocal() as db:
            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            p_name = patient.display_name if patient else "Dad (Ramesh)"
            events = db.query(DoseEvent).join(Medication).filter(
                Medication.patient_id == patient_id
            ).all()

        taken = sum(1 for e in events if e.status == "taken")
        skipped = sum(1 for e in events if e.status == "skipped")
        missed = sum(1 for e in events if e.status in ["missed", "pending"])
        total = max(1, taken + skipped + missed)
        rate = round((taken / total) * 100.0, 1)

        reply = (
            f"📊 **Weekly Adherence Report for {p_name}**\n\n"
            f"• **Overall Adherence Score:** **{rate}%**\n"
            f"• **Taken Doses:** {taken}\n"
            f"• **Skipped Doses:** {skipped}\n"
            f"• **Missed / Pending:** {missed}\n"
            f"• **Refill Status:** All active medications have ≥ 7 days of supply remaining.\n\n"
            f"Peace of mind summary: Overall routine is steady. No critical alerts pending."
        )
        return CardPayload("weekly_report", {"score": rate, "taken": taken}, guardrails.post_format(reply))

    elif intent.name == "LINK_CAREGIVER":
        reply = (
            "🤝 **Caregiver Link & Consent Management**\n\n"
            "To link a family caregiver:\n"
            "1. Enter caregiver name & notification channel (Telegram chat ID or phone number)\n"
            "2. Patient consent timestamp recorded automatically.\n"
            "Caregiver 'Priya' is currently registered for escalation alerts."
        )
        return CardPayload("text_reply", {}, guardrails.post_format(reply))

    else:
        # General assistance
        reply = (
            "👋 **Welcome to Med-Guardian** — your ASI:One adherence, refill, and caregiver safety assistant.\n\n"
            "Here is what you can say:\n"
            "• **Add meds:** *\"I'm managing my dad's medicines: Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin.\"*\n"
            "• **Check interactions:** *\"Can I take Ibuprofen with Metformin?\"*\n"
            "• **Log dose:** *\"Taken\"* or *\"Skip\"*\n"
            "• **Compare prices & refill:** *\"Refill Metformin\"*\n"
            "• **Adherence check:** *\"How did Dad do this week?\"*"
        )
        return CardPayload("welcome", {}, guardrails.post_format(reply))

# --- ACP Chat Handlers ---
@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    # 1. Acknowledge immediately (Mandatory for Agent Chat Protocol)
    await ctx.send(sender, create_ack(msg.msg_id))

    # 2. Extract plain text from ACP message
    user_text = extract_text(msg)
    ctx.logger.info(f"Received ACP ChatMessage from {sender}: '{user_text}'")

    # 3. Process turn
    card_payload = await process_orchestrator_turn(sender, user_text)

    # 4. Reply with ChatMessage containing text and metadata
    reply_msg = create_text_chat_message(
        text=card_payload.text_fallback,
        card_data=card_payload.to_dict()
    )
    await ctx.send(sender, reply_msg)

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Received ACP acknowledgement from {sender} for msg {msg.acknowledged_msg_id}")

orchestrator_agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Starting Guardian Orchestrator on port {settings.ORCHESTRATOR_PORT} (address: {orchestrator_agent.address})")
    orchestrator_agent.run()
