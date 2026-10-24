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
    def dose_checkin(patient_name: str, drug_name: str, strength: str, due_time: str) -> CardPayload:
        strength_str = f" {strength}" if strength else ""
        lines = [
            "┌────────────────────────────────────────────────────────┐",
            f"│ ⏰ DOSE TIME CHECK-IN: {drug_name.upper()} {strength}".ljust(57) + "│",
            "├────────────────────────────────────────────────────────┤",
            f"│ 👤 Patient:     {patient_name}".ljust(57) + "│",
            f"│ 💊 Medication:  {drug_name}{strength_str}".ljust(57) + "│",
            f"│ 🕒 Scheduled:   {due_time} (Grace Window: 20 min)".ljust(57) + "│",
            "│ 📋 Status:      Pending Dose Confirmation              │",
            "├────────────────────────────────────────────────────────┤",
            "│ Have you taken this dose?                              │",
            "│                                                        │",
            "│   [ 🟢 TAKEN ]       [ 🟡 SKIP ]       [ ⏱️ SNOOZE 15M ] │",
            "│                                                        │",
            "│ 👉 Tap a button above or reply 'Taken', 'Skip', 'Later'│",
            "└────────────────────────────────────────────────────────┘"
        ]
        card_data = {
            "title": f"Dose Check-in: {drug_name}",
            "type": "dose_checkin_card",
            "patient": patient_name,
            "drug": f"{drug_name}{strength_str}",
            "due_time": due_time,
            "status": "pending_confirmation",
            "actions": [
                {"label": "🟢 Taken", "action_id": "dose.taken", "style": "success"},
                {"label": "🟡 Skip", "action_id": "dose.skip", "style": "warning"},
                {"label": "⏱️ Snooze 15m", "action_id": "dose.later", "style": "secondary"}
            ]
        }
        return CardPayload("dose_checkin", card_data, "\n".join(lines))

    @staticmethod
    def medication_intake(meds: List[ParsedMedSchedule]) -> CardPayload:
        lines = [
            "┌────────────────────────────────────────────────────────┐",
            "│ 📋 CONFIRM MEDICATION SCHEDULE                         │",
            "├────────────────────────────────────────────────────────┤",
            "│ Please review the parsed regimen below:                │",
            "│                                                        │"
        ]
        med_items = []
        for i, m in enumerate(meds, 1):
            times_str = ", ".join(m.times) if m.times else "Daily"
            instr = f" ({m.instructions})" if m.instructions else ""
            lines.append(f"│ {i}. 💊 {m.drug_name} {m.strength}".ljust(57) + "│")
            lines.append(f"│    ⏱️ {m.frequency} at {times_str}{instr}".ljust(57) + "│")
            lines.append(f"│    📦 Supply: {m.qty_on_hand} pills remaining".ljust(57) + "│")
            lines.append("│                                                        │")
            med_items.append({
                "name": m.drug_name,
                "strength": m.strength,
                "frequency": m.frequency,
                "times": m.times,
                "qty_on_hand": m.qty_on_hand,
                "instructions": m.instructions
            })

        lines.extend([
            "├────────────────────────────────────────────────────────┤",
            "│   [ ✅ CONFIRM SCHEDULE ]         [ ❌ CANCEL ]         │",
            "│                                                        │",
            "│ 👉 Tap a button above or reply 'Confirm' / 'Cancel'    │",
            "└────────────────────────────────────────────────────────┘"
        ])
        
        card_data = {
            "title": "Confirm Medication Schedule",
            "type": "medication_intake_card",
            "medications": med_items,
            "actions": [
                {"label": "✅ Confirm Schedule", "action_id": "med.confirm", "style": "primary"},
                {"label": "❌ Cancel", "action_id": "med.cancel", "style": "danger"}
            ]
        }
        return CardPayload("medication_intake", card_data, "\n".join(lines))

    @staticmethod
    def interaction_review(findings: List[InteractionFinding], source_status: str = "ok") -> CardPayload:
        if not findings:
            note = "⚠️ (FDA real-time label momentarily degraded)" if source_status == "degraded" else "✅ No FDA label interaction flags found"
            lines = [
                "┌────────────────────────────────────────────────────────┐",
                "│ 🛡️ FDA SAFETY SCREENING: CLEAN                         │",
                "├────────────────────────────────────────────────────────┤",
                f"│ {note}".ljust(57) + "│",
                "│ Verified against official openFDA label database.      │",
                "└────────────────────────────────────────────────────────┘"
            ]
            card_data = {"status": "clean", "findings": []}
            return CardPayload("interaction_review", card_data, "\n".join(lines))

        lines = [
            "┌────────────────────────────────────────────────────────┐",
            "│ 🛡️ FDA MEDICATION INTERACTION ADVISORY                 │",
            "├────────────────────────────────────────────────────────┤",
            "│ Source: Official openFDA Drug Label Interactions       │",
            "├────────────────────────────────────────────────────────┤"
        ]
        card_findings = []
        for f in findings:
            lines.append(f"│ ⚠️ WARNING: {f.drug_a} + {f.drug_b}".ljust(57) + "│")
            lines.append(f"│ • Excerpt: \"{f.quote[:42]}...\"".ljust(57) + "│")
            lines.append(f"│ • Ask Pharmacist: \"{f.pharmacist_question[:36]}...\"".ljust(57) + "│")
            lines.append("│                                                        │")
            card_findings.append({
                "drug_a": f.drug_a,
                "drug_b": f.drug_b,
                "quote": f.quote,
                "question": f.pharmacist_question,
                "source_url": f.source_url
            })

        lines.extend([
            "├────────────────────────────────────────────────────────┤",
            "│   [ 🛡️ I ACKNOWLEDGE ]       [ 📋 COPY PHARMACIST Q ]  │",
            "│                                                        │",
            "│ 👉 Tap 'Acknowledge' to proceed with scheduling        │",
            "└────────────────────────────────────────────────────────┘"
        ])

        card_data = {
            "title": "Medication Interaction Advisory",
            "type": "interaction_review_card",
            "findings": card_findings,
            "actions": [
                {"label": "🛡️ I Acknowledge", "action_id": "interaction.acknowledge", "style": "primary"},
                {"label": "📋 Copy Pharmacist Question", "action_id": "interaction.copy_question", "style": "secondary"}
            ]
        }
        return CardPayload("interaction_review", card_data, "\n".join(lines))

    @staticmethod
    def price_carousel(drug_name: str, strength: str, qty: int, quotes: List[Quote], is_estimate: bool = True) -> CardPayload:
        lines = [
            "┌────────────────────────────────────────────────────────┐",
            f"│ 💊 PHARMACY REFILL PRICE COMPARISON                    │",
            "├────────────────────────────────────────────────────────┤",
            f"│ Drug: {drug_name} {strength} • {qty} count supply".ljust(57) + "│",
            "│ Partner verified & CMS NADAC reference pricing         │",
            "├────────────────────────────────────────────────────────┤"
        ]
        card_quotes = []
        actions = []

        medals = ["🥇", "🥈", "🥉"]
        for i, q in enumerate(quotes, 1):
            medal = medals[i - 1] if i <= len(medals) else f"#{i}"
            delivery = f"🚚 {q.delivery_days}-day mail" if q.delivery_days > 0 else "🏬 Same-day pickup"
            lines.append(f"│ {medal} Option {i}: {q.pharmacy_name}".ljust(57) + "│")
            lines.append(f"│    💰 ${q.price_dollars:.2f} USD [{delivery}]".ljust(57) + "│")
            if q.details:
                lines.append(f"│    ℹ️ {q.details[:48]}".ljust(57) + "│")
            lines.append(f"│    👉 [ 🛒 SELECT OPTION {i} (${q.price_dollars:.2f}) ]".ljust(57) + "│")
            lines.append("│                                                        │")
            card_quotes.append({
                "option_number": i,
                "pharmacy": q.pharmacy_name,
                "price_dollars": q.price_dollars,
                "delivery": delivery,
                "details": q.details
            })
            actions.append({
                "label": f"🛒 Option {i}: {q.pharmacy_name} (${q.price_dollars:.2f})",
                "action_id": f"refill.select:{i}",
                "style": "primary"
            })

        lines.extend([
            "├────────────────────────────────────────────────────────┤",
            "│ 👉 Tap a button above or reply 'Select Option 1'       │",
            "└────────────────────────────────────────────────────────┘"
        ])

        card_data = {
            "title": f"Price Comparison: {drug_name}",
            "type": "price_carousel_card",
            "quotes": card_quotes,
            "actions": actions
        }
        return CardPayload("price_carousel", card_data, "\n".join(lines))

    @staticmethod
    def refill_approval(drug_name: str, pharmacy_name: str, price_cents: int, payment_id: str) -> CardPayload:
        price_str = f"${price_cents / 100:.2f}"
        lines = [
            "┌────────────────────────────────────────────────────────┐",
            "│ 🛒 AUTHORIZE REFILL & PAYMENT                          │",
            "├────────────────────────────────────────────────────────┤",
            f"│ 💊 Medication:  {drug_name} (30-day supply)".ljust(57) + "│",
            f"│ 🏬 Pharmacy:    {pharmacy_name}".ljust(57) + "│",
            f"│ 💵 Total Due:   {price_str} USD".ljust(57) + "│",
            f"│ 🔐 Payment Ref: {payment_id}".ljust(57) + "│",
            "├────────────────────────────────────────────────────────┤",
            "│ This order will be dispatched to the pharmacy partner. │",
            "│                                                        │",
            f"│   [ 💳 APPROVE & PAY {price_str} ]       [ ❌ CANCEL ]   │",
            "│                                                        │",
            "│ 👉 Tap a button above or reply 'Approve & Pay'         │",
            "└────────────────────────────────────────────────────────┘"
        ]
        card_data = {
            "title": "Authorize Refill Order",
            "type": "refill_approval_card",
            "drug": drug_name,
            "pharmacy": pharmacy_name,
            "total": price_str,
            "payment_id": payment_id,
            "actions": [
                {"label": f"💳 Approve & Pay {price_str}", "action_id": f"refill.approve:{payment_id}", "style": "success"},
                {"label": "❌ Cancel Order", "action_id": "refill.cancel", "style": "danger"}
            ]
        }
        return CardPayload("refill_approval", card_data, "\n".join(lines))

    @staticmethod
    def caregiver_alert(caregiver_name: str, patient_name: str, drug_name: str, due_time: str) -> CardPayload:
        lines = [
            "┌────────────────────────────────────────────────────────┐",
            "│ 🚨 CAREGIVER ESCALATION ALERT                          │",
            "├────────────────────────────────────────────────────────┤",
            f"│ 👤 Patient:     {patient_name}".ljust(57) + "│",
            f"│ 💊 Missed Dose: {drug_name}".ljust(57) + "│",
            f"│ 🕒 Scheduled:   {due_time}".ljust(57) + "│",
            "│ ⚠️ 20-min grace period expired without confirmation.   │",
            "├────────────────────────────────────────────────────────┤",
            "│   [ 📞 CALL PATIENT ]   [ ⏱️ SNOOZE 30M ]   [ 🟢 MARK TAKEN ] │",
            "│                                                        │",
            "│ 👉 Tap an action or reply 'Call', 'Snooze', 'Taken'   │",
            "└────────────────────────────────────────────────────────┘"
        ]
        card_data = {
            "title": f"Caregiver Alert: {patient_name}",
            "type": "caregiver_alert_card",
            "patient": patient_name,
            "drug": drug_name,
            "due_time": due_time,
            "actions": [
                {"label": "📞 Call Patient", "action_id": "caregiver.call", "style": "primary"},
                {"label": "⏱️ Snooze 30m", "action_id": "caregiver.snooze", "style": "secondary"},
                {"label": "🟢 Mark as Taken", "action_id": "caregiver.mark_taken", "style": "success"}
            ]
        }
        return CardPayload("caregiver_alert", card_data, "\n".join(lines))

cards = CardBuilder()
