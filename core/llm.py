import re
import json
import logging
from typing import Dict, Any, List, Optional
from core.config import settings
from core.models import ParsedMedSchedule

logger = logging.getLogger("med-guardian.core.llm")

# Try to import OpenAI client for ASI1 LLM calls
try:
    from openai import AsyncOpenAI
    openai_available = True
except ImportError:
    openai_available = False

class IntentClassification:
    def __init__(self, name: str, entities: Dict[str, Any], is_confirmation: bool = False, raw_text: str = ""):
        self.name = name
        self.entities = entities
        self.is_confirmation = is_confirmation
        self.raw_text = raw_text

class LLMParser:
    def __init__(self):
        self.client = None
        if openai_available and settings.ASI1_API_KEY:
            self.client = AsyncOpenAI(
                api_key=settings.ASI1_API_KEY,
                base_url=settings.OPENAI_API_BASE
            )

    async def classify_and_extract(self, text: str, session_state: Dict[str, Any]) -> IntentClassification:
        normalized = text.strip().lower()
        pending = session_state.get("_pending_action", {})
        pending_type = pending.get("type", "")

        # 1. Action-ID or button-tap match (Card actions)
        if "med.confirm" in normalized or (pending_type == "medication_intake" and normalized in ["confirm", "yes", "save", "confirm schedule", "looks good"]):
            return IntentClassification("CONFIRM_SCHEDULE", {"action": "confirm"}, is_confirmation=True, raw_text=text)
        
        if "med.cancel" in normalized or (pending_type == "medication_intake" and normalized in ["cancel", "no", "abort"]):
            return IntentClassification("CONFIRM_SCHEDULE", {"action": "cancel"}, is_confirmation=True, raw_text=text)

        if "refill.approve" in normalized or (pending_type == "refill_approval" and any(k in normalized for k in ["approve", "approve & pay", "yes", "pay"])):
            order_id = pending.get("order_id", "")
            return IntentClassification("REFILL_APPROVE", {"action": "approve", "order_id": order_id}, is_confirmation=True, raw_text=text)

        if "refill.cancel" in normalized or (pending_type == "refill_approval" and any(k in normalized for k in ["cancel", "no", "abort"])):
            return IntentClassification("REFILL_APPROVE", {"action": "cancel"}, is_confirmation=True, raw_text=text)

        if "refill.select" in normalized or (pending_type == "price_carousel" and "option" in normalized):
            opt = re.search(r"(\d+)", normalized)
            option_idx = int(opt.group(1)) if opt else 1
            return IntentClassification("REFILL_SELECT", {"option_index": option_idx}, is_confirmation=True, raw_text=text)

        if any(action in normalized for action in ["taken", "skip", "skipped", "later", "mark taken", "dose.taken", "dose.skip"]):
            action = "taken" if "taken" in normalized else ("skipped" if "skip" in normalized else "later")
            return IntentClassification("LOG_DOSE", {"action": action}, raw_text=text)

        if any(k in normalized for k in ["how did dad do", "weekly report", "adherence report", "weekly adherence", "status", "adherence"]):
            return IntentClassification("WEEKLY_REPORT", {}, raw_text=text)

        if any(k in normalized for k in ["refill", "order more", "price comparison", "running low", "cheapest pharmacy"]):
            # Extract drug if specified
            drug_match = re.search(r"refill\s+([a-zA-Z]+)", normalized)
            drug_name = drug_match.group(1) if drug_match else "Metformin"
            return IntentClassification("REFILL", {"drug_name": drug_name}, raw_text=text)

        if "link caregiver" in normalized or "add caregiver" in normalized:
            return IntentClassification("LINK_CAREGIVER", {"raw": text}, raw_text=text)

        # 2. Check for LLM assisted parsing if client is configured
        if self.client:
            try:
                prompt = (
                    "You are a medical adherence assistant intent parser. Classify the user message into one of:\n"
                    "ADD_MEDICATIONS, CHECK_INTERACTION, LOG_DOSE, REFILL, WEEKLY_REPORT, GENERAL.\n"
                    "Extract entities (medications with name, strength, frequency, timing, qty_on_hand).\n"
                    "Return ONLY JSON: {\"intent\": \"...\", \"medications\": [...], \"entities\": {...}}"
                )
                response = await self.client.chat.completions.create(
                    model="asi1-mini",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text}
                    ],
                    response_format={"type": "json_object"}
                )
                parsed = json.loads(response.choices[0].message.content)
                intent_name = parsed.get("intent", "ADD_MEDICATIONS")
                return IntentClassification(intent_name, parsed, raw_text=text)
            except Exception as e:
                logger.warning(f"ASI1 LLM call failed or timed out: {e}. Falling back to rule-based parser.")

        # 3. Rule-based / Regex medication schedule parser (Robust Fallback)
        meds = self.extract_medications_rule_based(text)
        if meds:
            return IntentClassification("ADD_MEDICATIONS", {"medications": meds}, raw_text=text)

        if any(k in normalized for k in ["interact", "interaction", "safe together", "take with"]):
            return IntentClassification("CHECK_INTERACTION", {"raw": text}, raw_text=text)

        return IntentClassification("GENERAL", {"text": text}, raw_text=text)

    def extract_medications_rule_based(self, text: str) -> List[ParsedMedSchedule]:
        """
        Parses sentences like:
        - 'Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin.'
        - 'Add ibuprofen 400mg as needed'
        """
        results: List[ParsedMedSchedule] = []
        
        # Split by comma, semicolon, or period
        clauses = re.split(r"[,;.\n]+", text)
        
        # Look for runway info like 'has 10 days left of Metformin' or '10 days left'
        runway_map = {}
        runway_match = re.findall(r"(\d+)\s+days?\s+(?:left|of supply)?(?:\s+(?:of\s+)?([a-zA-Z]+))?", text, re.IGNORECASE)
        for days_str, drug in runway_match:
            days = int(days_str)
            if drug:
                runway_map[drug.lower()] = days
            else:
                runway_map["_global_days"] = days

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            
            # Pattern: [Add] [Drug] [Strength] [Frequency/Timing]
            # e.g. Metformin 500mg twice daily
            pattern = r"(?:add\s+)?([A-Za-z]+)\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)?)\s*(twice daily|once daily|daily|morning|night|evening|afternoon|bedtime|as needed|prn)?"
            match = re.search(pattern, clause, re.IGNORECASE)
            if match:
                drug_name = match.group(1).capitalize()
                strength = match.group(2).strip()
                freq_raw = (match.group(3) or "daily").lower()

                # Filter out false positive common English words
                if drug_name.lower() in ["i", "im", "i'm", "managing", "dad", "mom", "he", "she", "take", "has"]:
                    continue

                times = ["08:00"]
                frequency = "daily"
                instructions = ""

                if "twice" in freq_raw:
                    frequency = "twice daily"
                    times = ["08:00", "20:00"]
                    instructions = "Take with meals"
                elif "morning" in freq_raw:
                    frequency = "daily"
                    times = ["08:00"]
                    instructions = "Take in morning"
                elif "night" in freq_raw or "evening" in freq_raw:
                    frequency = "daily"
                    times = ["21:00"]
                    instructions = "Take at night"
                elif "as needed" in freq_raw or "prn" in freq_raw:
                    frequency = "as needed"
                    times = []
                    instructions = "Take as needed for pain/symptoms"

                # Check days of supply left
                days_left = runway_map.get(drug_name.lower(), runway_map.get("_global_days", 30))
                doses_per_day = len(times) if times else 1
                qty_on_hand = days_left * doses_per_day

                results.append(ParsedMedSchedule(
                    drug_name=drug_name,
                    strength=strength,
                    frequency=frequency,
                    times=times,
                    qty_on_hand=qty_on_hand,
                    qty_per_dose=1,
                    instructions=instructions
                ))

        return results

llm_parser = LLMParser()
