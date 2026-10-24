import re
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from core.config import settings
from core.models import ParsedMedSchedule

logger = logging.getLogger("med-guardian.core.llm")

# LLM TIMEOUT — never wait more than 5 seconds
LLM_TIMEOUT_SECONDS = 5

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
                base_url=settings.OPENAI_API_BASE,
                timeout=LLM_TIMEOUT_SECONDS,
            )

    async def classify_and_extract(self, text: str, session_state: Dict[str, Any]) -> IntentClassification:
        normalized = text.strip().lower()
        pending = session_state.get("_pending_action", {})
        pending_type = pending.get("type", "")

        # ── FAST PATH: all rule-based checks run BEFORE any LLM call ──────────

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

        # Check dose / dose status inquiries ("Did I take my medicine?", "Is it time for pills?", etc.)
        check_dose_patterns = [
            "did i take", "have i taken", "did dad take", "was the medicine taken",
            "is it time for", "time to take", "check dose", "check my dose",
            "what dose", "what medicines are due", "any medicine due",
            "next dose", "remind me to take", "do i need to take", "should i take my pill",
            "dose status", "any pills due", "missed dose", "did i miss"
        ]
        if any(k in normalized for k in check_dose_patterns):
            return IntentClassification("CHECK_DOSE", {}, raw_text=text)

        # Dose confirmation actions ("Taken", "Skip", "Later", etc.)
        if any(action in normalized for action in ["mark taken", "dose.taken", "dose.skip", "snooze", "remind in 15m"]) or normalized in ["taken", "i took it", "already taken", "skip", "skipped", "later"]:
            action = "taken" if any(w in normalized for w in ["taken", "took"]) else ("skipped" if "skip" in normalized else "later")
            return IntentClassification("LOG_DOSE", {"action": action}, raw_text=text)

        if any(k in normalized for k in ["how did dad do", "weekly report", "adherence report", "weekly adherence", "status", "adherence"]):
            return IntentClassification("WEEKLY_REPORT", {}, raw_text=text)

        if any(k in normalized for k in ["refill", "order more", "price comparison", "running low", "cheapest pharmacy"]):
            drug_match = re.search(r"refill\s+([a-zA-Z]+)", normalized)
            drug_name = drug_match.group(1) if drug_match else "Metformin"
            return IntentClassification("REFILL", {"drug_name": drug_name}, raw_text=text)

        if "link caregiver" in normalized or "add caregiver" in normalized:
            return IntentClassification("LINK_CAREGIVER", {"raw": text}, raw_text=text)

        if any(k in normalized for k in ["interact", "interaction", "safe together", "take with", "can i take"]):
            return IntentClassification("CHECK_INTERACTION", {"raw": text}, raw_text=text)

        # Rule-based medication schedule parser
        meds = self.extract_medications_rule_based(text)
        if meds:
            return IntentClassification("ADD_MEDICATIONS", {"medications": meds}, raw_text=text)

        # ── FAST PATH: clearly conversational messages → GENERAL intent ────────
        # Route these directly to the conversational response handler
        general_patterns = [
            "hello", "hi ", "hey", "good morning", "good afternoon", "good evening",
            "howdy", "thank", "thanks", "bye", "goodbye", "see you",
            "how are you", "what's up", "who are you", "what are you",
            "what can you do", "help me", "what do you do",
            "your name", "tell me about yourself",
        ]
        if any(p in normalized for p in general_patterns) or normalized in ["hi", "hey", "yo", "sup"]:
            return IntentClassification("GENERAL", {"text": text}, raw_text=text)

        # ── SLOW PATH: LLM only for genuinely ambiguous free-form text ─────────
        # Only used if ASI1_API_KEY is set AND the message wasn't handled above
        if self.client:
            try:
                prompt = (
                    "You are a medical adherence assistant intent parser. Classify the user message into one of:\n"
                    "ADD_MEDICATIONS, CHECK_INTERACTION, LOG_DOSE, REFILL, WEEKLY_REPORT, GENERAL.\n"
                    "Extract entities (medications with name, strength, frequency, timing, qty_on_hand).\n"
                    "Return ONLY JSON: {\"intent\": \"...\", \"medications\": [...], \"entities\": {...}}"
                )
                llm_coro = self.client.chat.completions.create(
                    model="asi1-mini",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=256,     # keep responses fast and focused
                )
                response = await asyncio.wait_for(llm_coro, timeout=LLM_TIMEOUT_SECONDS)
                parsed = json.loads(response.choices[0].message.content)
                intent_name = parsed.get("intent", "GENERAL")
                return IntentClassification(intent_name, parsed, raw_text=text)
            except asyncio.TimeoutError:
                logger.warning("ASI1 LLM timed out after 5s — using GENERAL fallback.")
            except Exception as e:
                logger.warning(f"ASI1 LLM call failed: {e} — using GENERAL fallback.")

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

    async def generate_response(self, text: str, context: str = "", patient_meds: list = None) -> str:
        """
        Generate a conversational response for general/unrecognized messages.
        Uses the LLM when available, falls back to smart rule-based responses.
        """
        now_utc = datetime.now(timezone.utc)
        current_time_str = now_utc.strftime("%A, %B %d, %Y at %I:%M:%S %p UTC")

        if self.client:
            try:
                system_prompt = (
                    "You are Med-Guardian, a friendly and knowledgeable medication adherence assistant. "
                    "You help patients and caregivers manage medication schedules, track doses, check interactions, "
                    "compare pharmacy prices, and monitor adherence.\n\n"
                    f"CURRENT REAL-TIME CLOCK:\n"
                    f"- Current Real-Time Date & Time: {current_time_str}\n"
                    f"- IMPORTANT: When asked about the date, day, month, year, or time, always use this real-time clock.\n\n"
                    "IMPORTANT RULES:\n"
                    "- You are NOT a doctor. Never diagnose, prescribe, or recommend dosage changes.\n"
                    "- For medical emergencies, always tell the user to call 911.\n"
                    "- You CAN answer general health/wellness questions with standard public knowledge.\n"
                    "- You CAN explain what medications are commonly used for (public info).\n"
                    "- You CAN help with scheduling, reminders, adherence tips, and pharmacy logistics.\n"
                    "- Be warm, supportive, and concise.\n"
                    "- Use emoji sparingly to keep responses friendly.\n"
                    "- Always add a gentle reminder to consult their doctor for medical decisions.\n\n"
                )
                if patient_meds:
                    med_list = ", ".join(patient_meds)
                    system_prompt += f"The patient currently takes: {med_list}.\n"
                if context:
                    system_prompt += f"Additional context: {context}\n"

                llm_coro = self.client.chat.completions.create(
                    model="asi1-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=512,
                )
                response = await asyncio.wait_for(llm_coro, timeout=LLM_TIMEOUT_SECONDS)
                reply = response.choices[0].message.content.strip()
                if reply:
                    return reply
            except asyncio.TimeoutError:
                logger.warning("ASI1 LLM timed out generating response — using fallback.")
            except Exception as e:
                logger.warning(f"ASI1 LLM response generation failed: {e} — using fallback.")

        # Smart rule-based fallback when no LLM is available
        return self._smart_fallback(text)

    def _smart_fallback(self, text: str) -> str:
        """
        Intelligent keyword-based fallback responses for when no LLM API key is configured.
        Actually responds to what the user asked instead of showing the generic welcome.
        """
        normalized = text.strip().lower()

        # Real-time date and time inquiries
        if any(p in normalized for p in ["what time is it", "what's the time", "current time", "what day is it", "what date is it", "today's date", "what is today's date", "what is the date", "what date is today"]):
            now_utc = datetime.now(timezone.utc)
            return (
                f"🕒 **Current Real-Time Clock**\n\n"
                f"• **Date:** {now_utc.strftime('%A, %B %d, %Y')}\n"
                f"• **Time:** {now_utc.strftime('%I:%M:%S %p UTC')}\n\n"
                f"All dose tracking, reminder grace periods, and escalation timers run on this real-time clock."
            )

        # Greetings
        if any(g in normalized for g in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy", "sup"]):
            return (
                "👋 **Hello!** Welcome to Med-Guardian — your medication adherence and caregiver safety assistant.\n\n"
                "Here's what I can help you with:\n"
                "• **Add medications** — Tell me what medicines you're managing\n"
                "• **Check interactions** — Ask about drug combinations\n"
                "• **Log doses** — Say \"Taken\" or \"Skip\"\n"
                "• **Refill medications** — Compare pharmacy prices\n"
                "• **Weekly adherence report** — See how you're doing\n\n"
                "Just type naturally and I'll do my best to help! 😊"
            )

        # Thanks / gratitude
        if any(w in normalized for w in ["thank", "thanks", "thx", "appreciate"]):
            return "😊 You're welcome! I'm here whenever you need help with your medications. Don't hesitate to ask!"

        # How are you / status
        if any(p in normalized for p in ["how are you", "how do you do", "what's up", "how's it going"]):
            return (
                "I'm doing great, thank you for asking! 😊\n\n"
                "I'm here and ready to help you manage medications, track doses, "
                "check for drug interactions, or compare pharmacy prices. What can I do for you today?"
            )

        # What can you do / help
        if any(p in normalized for p in ["what can you do", "help me", "what do you do", "features", "capabilities", "how do you work", "how does this work"]):
            return (
                "🏥 **Here's everything I can help with:**\n\n"
                "📋 **Medication Management**\n"
                "• Add and track medications with schedules\n"
                "• Parse natural language like: *\"Metformin 500mg twice daily\"*\n\n"
                "🛡️ **Safety Checks**\n"
                "• Screen for drug-drug interactions using FDA data\n"
                "• Flag potential concerns for pharmacist discussion\n\n"
                "⏰ **Dose Tracking**\n"
                "• Log doses as taken, skipped, or snoozed\n"
                "• Track adherence over time\n\n"
                "💊 **Pharmacy & Refills**\n"
                "• Compare prices across pharmacies\n"
                "• Place refill orders with price estimates\n\n"
                "👨‍👩‍👦 **Caregiver Support**\n"
                "• Link caregivers for missed-dose alerts\n"
                "• Weekly adherence reports\n\n"
                "Just ask me anything — I understand natural language!"
            )

        # Who are you / about
        if any(p in normalized for p in ["who are you", "what are you", "about you", "your name", "introduce yourself"]):
            return (
                "🤖 I'm **Med-Guardian**, your ASI:One-powered medication adherence assistant!\n\n"
                "I help patients and caregivers:\n"
                "• Organize medication schedules\n"
                "• Track dose adherence\n"
                "• Screen for drug interactions (using real FDA data)\n"
                "• Compare pharmacy prices for refills\n"
                "• Alert caregivers about missed doses\n\n"
                "I'm built on the Fetch.ai agent network and I'm here to make medication management easier and safer."
            )

        # Questions about specific medication info (general knowledge)
        if any(p in normalized for p in ["what is", "what's", "tell me about", "explain", "information about", "info on", "describe"]):
            return (
                f"That's a great question! While I can help with medication scheduling, "
                f"interactions, and adherence tracking, for detailed medical information "
                f"I'd recommend checking with your pharmacist or a trusted source like "
                f"**MedlinePlus** (medlineplus.gov) or **WebMD**.\n\n"
                f"Meanwhile, I can help if you want to:\n"
                f"• **Add this medication** to your schedule\n"
                f"• **Check interactions** with your current meds\n"
                f"• **Look up refill prices** at nearby pharmacies\n\n"
                f"Just let me know! 💊"
            )

        # Questions about side effects
        if any(p in normalized for p in ["side effect", "adverse", "reaction", "allergy", "allergic"]):
            return (
                "⚕️ Side effects and allergic reactions are important to discuss with your doctor or pharmacist.\n\n"
                "I can help you:\n"
                "• **Check drug interactions** between your medications\n"
                "• **Log if you skip a dose** due to side effects\n"
                "• **Connect with your caregiver** if you're feeling unwell\n\n"
                "If you're experiencing a severe reaction, please **call 911** or go to the nearest ER immediately."
            )

        # Timing questions
        if any(p in normalized for p in ["when should i", "best time to take", "morning or night", "before or after", "with food", "empty stomach"]):
            return (
                "⏰ Great question about medication timing!\n\n"
                "General tips:\n"
                "• **With food**: Many medications (like Metformin) are better absorbed with meals\n"
                "• **Morning meds**: Blood pressure and thyroid meds often work best in the morning\n"
                "• **Night meds**: Statins (like Atorvastatin) are often taken at bedtime\n"
                "• **Consistency**: Taking meds at the same time daily improves effectiveness\n\n"
                "For specific timing, always follow your doctor's instructions. "
                "Want me to help set up a schedule? Just tell me your medications!"
            )

        # Goodbye
        if any(w in normalized for w in ["bye", "goodbye", "see you", "later", "gotta go", "good night"]):
            return "👋 Take care! Remember to take your medications on time. I'm here whenever you need me!"

        # Yes/no without context
        if normalized in ["yes", "no", "ok", "okay", "sure", "alright", "yep", "nope"]:
            return (
                "Got it! Is there anything specific I can help you with? You can:\n"
                "• Tell me about your medications to set up a schedule\n"
                "• Ask about drug interactions\n"
                "• Check refill prices\n"
                "• View your adherence report"
            )

        # Catch-all: actually acknowledge what they said
        return (
            f"I appreciate your message! I'm Med-Guardian, focused on medication management.\n\n"
            f"I may not fully understand that request, but here's how I can help:\n"
            f"• **Add medications**: *\"I take Metformin 500mg twice daily\"*\n"
            f"• **Check interactions**: *\"Can I take Ibuprofen with Metformin?\"*\n"
            f"• **Log a dose**: Say *\"Taken\"* or *\"Skip\"*\n"
            f"• **Refill**: *\"Refill Metformin\"*\n"
            f"• **Adherence report**: *\"How did Dad do this week?\"*\n\n"
            f"Try rephrasing or ask me one of the above! 😊"
        )

llm_parser = LLMParser()
