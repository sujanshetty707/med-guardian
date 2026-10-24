from typing import List, Dict, Any, Optional
from core.models import ParsedMedSchedule, InteractionFinding, Quote, RunwayItem

class CardPayload:
    def __init__(self, card_type: str, card_data: Dict[str, Any], text_fallback: str, card_kind: str = "detail"):
        self.card_type = card_type
        self.card_data = card_data
        self.text_fallback = text_fallback
        self.card_kind = card_kind

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "interactive_card",
            "card_kind": self.card_kind,
            "card_type": self.card_type,
            "data": self.card_data,
            "text": self.text_fallback
        }

class CardBuilder:
    @staticmethod
    def dose_checkin(patient_name: str, drug_name: str, strength: str, due_time: str) -> CardPayload:
        strength_str = f" {strength}" if strength else ""
        text = (
            f"⏰ **Dose Time: {drug_name}{strength_str}**\n\n"
            f"• **Patient:** {patient_name}\n"
            f"• **Medication:** {drug_name}{strength_str}\n"
            f"• **Scheduled:** {due_time} (Grace Window: 20 min)\n"
            f"• **Status:** Pending dose confirmation\n\n"
            f"Have you taken this dose?\n"
            f"👉 Click **Taken**, **Skip**, or **Snooze 15m** below."
        )
        buttons = [
            {"label": "Taken", "action": "dose.taken", "style": "primary"},
            {"label": "Skip", "action": "dose.skip", "style": "warning"},
            {"label": "Snooze 15m", "action": "dose.later", "style": "secondary"}
        ]
        card_data = {
            "title": f"Dose Check-in: {drug_name}",
            "description": f"Scheduled dose of {drug_name}{strength_str} for {patient_name} at {due_time}.",
            "patient": patient_name,
            "drug": f"{drug_name}{strength_str}",
            "due_time": due_time,
            "status": "pending_confirmation",
            "buttons": buttons,
            "actions": [
                {"label": "Taken", "action_id": "dose.taken", "style": "primary"},
                {"label": "Skip", "action_id": "dose.skip", "style": "warning"},
                {"label": "Snooze 15m", "action_id": "dose.later", "style": "secondary"}
            ]
        }
        return CardPayload("dose_checkin", card_data, text, card_kind="detail")

    @staticmethod
    def medication_intake(meds: List[ParsedMedSchedule]) -> CardPayload:
        lines = [
            "📋 **Medication Schedule Review**\n",
            "Please confirm your parsed prescription schedule:\n"
        ]
        med_items = []
        for i, m in enumerate(meds, 1):
            times_str = ", ".join(m.times) if m.times else "Daily"
            instr = f" ({m.instructions})" if m.instructions else ""
            lines.append(f"**{i}. {m.drug_name}** `{m.strength}`")
            lines.append(f"   • Frequency: {m.frequency} at {times_str}{instr}")
            lines.append(f"   • Supply runway: {m.qty_on_hand} pills remaining")
            lines.append("")
            med_items.append({
                "name": m.drug_name,
                "strength": m.strength,
                "frequency": m.frequency,
                "times": m.times,
                "qty_on_hand": m.qty_on_hand,
                "instructions": m.instructions
            })

        lines.append("👉 Click **Confirm Schedule** to save and activate automated reminders, or **Cancel** to abort.")
        
        buttons = [
            {"label": "Confirm Schedule", "action": "med.confirm", "style": "primary"},
            {"label": "Cancel", "action": "med.cancel", "style": "danger"}
        ]
        card_data = {
            "title": "Confirm Medication Schedule",
            "description": f"Review and activate schedule for {len(meds)} medications.",
            "medications": med_items,
            "buttons": buttons,
            "actions": [
                {"label": "Confirm Schedule", "action_id": "med.confirm", "style": "primary"},
                {"label": "Cancel", "action_id": "med.cancel", "style": "danger"}
            ]
        }
        return CardPayload("medication_intake", card_data, "\n".join(lines), card_kind="detail")

    @staticmethod
    def interaction_review(findings: List[InteractionFinding], source_status: str = "ok") -> CardPayload:
        if not findings:
            text = (
                "🛡️ **FDA Safety Screening: Clean**\n\n"
                "✅ No interaction warnings flagged in the official FDA label database for these medications.\n"
                "Always verify with your doctor or pharmacist when starting any new drug."
            )
            card_data = {
                "title": "Safety Screening Clean",
                "description": "No FDA drug-drug interaction warnings found.",
                "status": "clean",
                "findings": []
            }
            return CardPayload("interaction_review", card_data, text, card_kind="detail")

        lines = [
            "🛡️ **FDA Medication Interaction Advisory**\n",
            "Source: Official openFDA Drug Label Interactions\n"
        ]
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

        lines.append("👉 Click **I Acknowledge** to proceed with scheduling.")
        buttons = [
            {"label": "I Acknowledge", "action": "interaction.acknowledge", "style": "primary"},
            {"label": "Copy Pharmacist Question", "action": "interaction.copy_question", "style": "secondary"}
        ]
        card_data = {
            "title": "Medication Interaction Advisory",
            "description": f"Found {len(findings)} potential interaction warnings in FDA drug labels.",
            "findings": card_findings,
            "buttons": buttons,
            "actions": [
                {"label": "I Acknowledge", "action_id": "interaction.acknowledge", "style": "primary"},
                {"label": "Copy Pharmacist Question", "action_id": "interaction.copy_question", "style": "secondary"}
            ]
        }
        return CardPayload("interaction_review", card_data, "\n".join(lines), card_kind="detail")

    @staticmethod
    def price_carousel(drug_name: str, strength: str, qty: int, quotes: List[Quote], is_estimate: bool = True) -> CardPayload:
        lines = [
            f"💊 **Pharmacy Refill Comparison: {drug_name} {strength}**\n",
            f"Quantity: {qty} count supply • Partner verified & CMS NADAC reference pricing\n"
        ]
        items = []
        buttons = []
        actions = []

        for i, q in enumerate(quotes, 1):
            delivery = f"Delivered in {q.delivery_days} days" if q.delivery_days > 0 else "Same-day pickup"
            lines.append(f"**Option {i}: {q.pharmacy_name}**")
            lines.append(f"• Price: **${q.price_dollars:.2f} USD** ({delivery})")
            if q.details:
                lines.append(f"• Details: {q.details}")
            lines.append("")

            btn = {
                "label": f"Select {q.pharmacy_name} (${q.price_dollars:.2f})",
                "action": f"refill.select:{i}",
                "style": "primary"
            }
            buttons.append(btn)
            actions.append({
                "label": f"Select {q.pharmacy_name} (${q.price_dollars:.2f})",
                "action_id": f"refill.select:{i}",
                "style": "primary"
            })
            items.append({
                "id": f"option_{i}",
                "title": q.pharmacy_name,
                "price": f"${q.price_dollars:.2f}",
                "delivery": delivery,
                "details": q.details or "",
                "buttons": [btn]
            })

        lines.append("👉 Tap a pharmacy button below to proceed to checkout.")

        card_data = {
            "title": f"Price Comparison: {drug_name}",
            "description": f"Refill quotes for {drug_name} {strength} ({qty} pills)",
            "items": items,
            "buttons": buttons,
            "actions": actions
        }
        return CardPayload("price_carousel", card_data, "\n".join(lines), card_kind="carousel")

    @staticmethod
    def refill_approval(drug_name: str, pharmacy_name: str, price_cents: int, payment_id: str) -> CardPayload:
        price_str = f"${price_cents / 100:.2f}"
        lines = [
            "🛒 **Authorize Refill & Payment**\n",
            f"• **Medication:** {drug_name} (30-day supply)",
            f"• **Pharmacy Partner:** {pharmacy_name}",
            f"• **Total Authorized:** **{price_str} USD**",
            f"• **Payment Protocol Request:** `{payment_id}`\n",
            "This order will be submitted directly to the pharmacy partner.",
            f"\n👉 Click **Approve & Pay {price_str}** below to authorize:"
        ]
        buttons = [
            {"label": f"Approve & Pay {price_str}", "action": f"refill.approve:{payment_id}", "style": "success"},
            {"label": "Cancel Order", "action": "refill.cancel", "style": "danger"}
        ]
        card_data = {
            "title": "Authorize Refill Order",
            "description": f"Payment authorization of {price_str} for {drug_name} via {pharmacy_name}.",
            "drug": drug_name,
            "pharmacy": pharmacy_name,
            "total": price_str,
            "payment_id": payment_id,
            "buttons": buttons,
            "actions": [
                {"label": f"Approve & Pay {price_str}", "action_id": f"refill.approve:{payment_id}", "style": "success"},
                {"label": "Cancel Order", "action_id": "refill.cancel", "style": "danger"}
            ]
        }
        return CardPayload("refill_approval", card_data, "\n".join(lines), card_kind="detail")

    @staticmethod
    def caregiver_alert(caregiver_name: str, patient_name: str, drug_name: str, due_time: str) -> CardPayload:
        text = (
            f"🚨 **Caregiver Escalation Alert: Missed Dose for {patient_name}**\n\n"
            f"• **Patient:** {patient_name}\n"
            f"• **Missed Dose:** {drug_name}\n"
            f"• **Scheduled:** {due_time}\n"
            f"• **Status:** Grace period expired without dose confirmation.\n\n"
            f"👉 Choose an escalation action below:"
        )
        buttons = [
            {"label": "Call Patient", "action": "caregiver.call", "style": "primary"},
            {"label": "Snooze 30m", "action": "caregiver.snooze", "style": "secondary"},
            {"label": "Mark as Taken", "action": "caregiver.mark_taken", "style": "success"}
        ]
        card_data = {
            "title": f"Caregiver Alert: {patient_name}",
            "description": f"Missed dose of {drug_name} due at {due_time}.",
            "patient": patient_name,
            "drug": drug_name,
            "due_time": due_time,
            "buttons": buttons,
            "actions": [
                {"label": "Call Patient", "action_id": "caregiver.call", "style": "primary"},
                {"label": "Snooze 30m", "action_id": "caregiver.snooze", "style": "secondary"},
                {"label": "Mark as Taken", "action_id": "caregiver.mark_taken", "style": "success"}
            ]
        }
        return CardPayload("caregiver_alert", card_data, text, card_kind="detail")

cards = CardBuilder()
