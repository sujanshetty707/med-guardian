from typing import List, Dict, Any, Optional
from core.models import ParsedMedSchedule, InteractionFinding, Quote, RunwayItem

class CardPayload:
    def __init__(self, card_type: str, card_data: Dict[str, Any], text_fallback: str):
        self.card_type = card_type
        self.card_data = card_data
        self.text_fallback = text_fallback

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "interactive_card",
            "card_type": self.card_type,
            "data": self.card_data,
            "text": self.text_fallback
        }

class CardBuilder:
    @staticmethod
    def medication_intake(meds: List[ParsedMedSchedule]) -> CardPayload:
        med_items = []
        lines = ["📋 **Medication Schedule Confirmation**\n", "Please review the parsed medications:"]
        for i, m in enumerate(meds, 1):
            times_str = ", ".join(m.times) if m.times else "Daily"
            instr = f" ({m.instructions})" if m.instructions else ""
            lines.append(f"{i}. **{m.drug_name}** {m.strength} — {m.frequency} at {times_str}{instr} [Supply: {m.qty_on_hand} pills]")
            med_items.append({
                "name": m.drug_name,
                "strength": m.strength,
                "frequency": m.frequency,
                "times": m.times,
                "qty_on_hand": m.qty_on_hand,
                "instructions": m.instructions
            })

        lines.append("\n👉 Reply **'Confirm'** to save this schedule, or **'Edit'** to modify.")
        
        card_data = {
            "title": "Confirm Medication Schedule",
            "medications": med_items,
            "actions": [
                {"label": "Confirm Schedule", "action_id": "med.confirm", "style": "primary"},
                {"label": "Edit Details", "action_id": "med.edit", "style": "secondary"},
                {"label": "Cancel", "action_id": "med.cancel", "style": "danger"}
            ]
        }
        return CardPayload("medication_intake", card_data, "\n".join(lines))

    @staticmethod
    def interaction_review(findings: List[InteractionFinding], source_status: str = "ok") -> CardPayload:
        lines = ["🛡️ **Medication Interaction Screening**\n"]
        if not findings:
            if source_status == "degraded":
                lines.append("⚠️ *Note: Real-time FDA label checking was momentarily degraded. Please discuss any combinations with your pharmacist.*")
            else:
                lines.append("✅ **No interaction warnings flagged** in the official FDA label data for these medications.")
                lines.append("Always verify with your doctor or pharmacist when starting any new supplement or drug.")
            card_data = {"status": "clean", "findings": []}
            return CardPayload("interaction_review", card_data, "\n".join(lines))

        card_findings = []
        for f in findings:
            lines.append(f"⚠️ **{f.drug_a} + {f.drug_b}**")
            lines.append(f"• **Label Excerpt:** \"{f.quote}\"")
            lines.append(f"• **Pharmacist Question to Ask:** *\"{f.pharmacist_question}\"*")
            if f.source_url:
                lines.append(f"• **Source:** [FDA Drug Label]({f.source_url})")
            lines.append("")
            card_findings.append({
                "drug_a": f.drug_a,
                "drug_b": f.drug_b,
                "quote": f.quote,
                "question": f.pharmacist_question,
                "source_url": f.source_url
            })

        lines.append("👉 Reply **'Acknowledge'** to proceed, or copy the question above to ask your pharmacist.")

        card_data = {
            "title": "Medication Interaction Advisory",
            "findings": card_findings,
            "actions": [
                {"label": "I Acknowledge", "action_id": "interaction.acknowledge", "style": "primary"},
                {"label": "Copy Pharmacist Question", "action_id": "interaction.copy_question", "style": "secondary"}
            ]
        }
        return CardPayload("interaction_review", card_data, "\n".join(lines))

    @staticmethod
    def dose_checkin(patient_name: str, drug_name: str, strength: str, due_time: str) -> CardPayload:
        lines = [
            f"⏰ **Dose Reminder for {patient_name}**\n",
            f"It's time for **{drug_name} {strength}** (scheduled for {due_time}).\n",
            "Have you taken this dose?",
            "👉 Reply **'Taken'**, **'Skip'**, or **'Later'**."
        ]
        card_data = {
            "title": f"Dose Time: {drug_name}",
            "patient": patient_name,
            "drug": f"{drug_name} {strength}",
            "due_time": due_time,
            "actions": [
                {"label": "Taken", "action_id": "dose.taken", "style": "success"},
                {"label": "Skip", "action_id": "dose.skip", "style": "warning"},
                {"label": "Remind in 15m", "action_id": "dose.later", "style": "secondary"}
            ]
        }
        return CardPayload("dose_checkin", card_data, "\n".join(lines))

    @staticmethod
    def price_carousel(drug_name: str, strength: str, qty: int, quotes: List[Quote], is_estimate: bool = True) -> CardPayload:
        lines = [f"💊 **Pharmacy Refill Comparison for {drug_name} {strength} ({qty} count)**\n"]
        if is_estimate:
            lines.append("*(Note: Showing verified pharmacy pricing estimates)*\n")

        card_quotes = []
        for i, q in enumerate(quotes, 1):
            delivery = f"Delivered in {q.delivery_days} days" if q.delivery_days > 0 else "Same-day pickup"
            lines.append(f"**Option {i}: {q.pharmacy_name}**")
            lines.append(f"• Price: **${q.price_dollars:.2f}** ({delivery})")
            if q.details:
                lines.append(f"• Details: {q.details}")
            lines.append("")
            card_quotes.append({
                "option_number": i,
                "pharmacy": q.pharmacy_name,
                "price_dollars": q.price_dollars,
                "delivery": delivery,
                "details": q.details
            })

        lines.append("👉 Reply with **'Select Option 1'**, **'Select Option 2'**, etc., to proceed with refill checkout.")

        card_data = {
            "title": f"Price Comparison: {drug_name}",
            "quotes": card_quotes,
            "actions": [
                {"label": f"Select {q.pharmacy_name} (${q.price_dollars:.2f})", "action_id": f"refill.select:{i}", "style": "primary"}
                for i, q in enumerate(quotes, 1)
            ]
        }
        return CardPayload("price_carousel", card_data, "\n".join(lines))

    @staticmethod
    def refill_approval(drug_name: str, pharmacy_name: str, price_cents: int, payment_id: str) -> CardPayload:
        price_str = f"${price_cents / 100:.2f}"
        lines = [
            "🛒 **Refill Order & Payment Approval**\n",
            f"• Medication: **{drug_name}**",
            f"• Pharmacy: **{pharmacy_name}**",
            f"• Total Order: **{price_str}**",
            f"• Payment Protocol Request: `{payment_id}`\n",
            "This order will be submitted directly to the pharmacy partner.",
            "👉 Reply **'Approve & Pay'** to authorize the charge, or **'Cancel'** to abort."
        ]
        card_data = {
            "title": "Authorize Refill Order",
            "drug": drug_name,
            "pharmacy": pharmacy_name,
            "total": price_str,
            "payment_id": payment_id,
            "actions": [
                {"label": f"Approve & Pay {price_str}", "action_id": f"refill.approve:{payment_id}", "style": "success"},
                {"label": "Cancel Order", "action_id": "refill.cancel", "style": "danger"}
            ]
        }
        return CardPayload("refill_approval", card_data, "\n".join(lines))

    @staticmethod
    def caregiver_alert(caregiver_name: str, patient_name: str, drug_name: str, due_time: str) -> CardPayload:
        lines = [
            f"🚨 **Caregiver Alert: Missed Dose for {patient_name}**\n",
            f"{patient_name} missed scheduled dose of **{drug_name}** due at {due_time}.",
            "Grace period expired without dose confirmation.\n",
            "👉 Available actions: Reply **'Call'**, **'Snooze 30m'**, or **'Mark Taken'**."
        ]
        card_data = {
            "title": f"Caregiver Alert: {patient_name}",
            "patient": patient_name,
            "drug": drug_name,
            "due_time": due_time,
            "actions": [
                {"label": f"Call {patient_name}", "action_id": "caregiver.call", "style": "primary"},
                {"label": "Snooze 30m", "action_id": "caregiver.snooze", "style": "secondary"},
                {"label": "Mark as Taken", "action_id": "caregiver.mark_taken", "style": "success"}
            ]
        }
        return CardPayload("caregiver_alert", card_data, "\n".join(lines))

cards = CardBuilder()
