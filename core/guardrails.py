import re
from typing import Optional, NamedTuple

class GuardrailResult(NamedTuple):
    block: bool
    response: Optional[str] = None
    reason: Optional[str] = None

EMERGENCY_KEYWORDS = [
    r"\boverdose\b",
    r"\bchest pain\b",
    r"\bcan'?t breathe\b",
    r"\bdifficulty breathing\b",
    r"\bpassed out\b",
    r"\bunconscious\b",
    r"\bsevere allergic\b",
    r"\banaphylaxis\b",
    r"\bpoisoning\b",
    r"\bswallowed the whole bottle\b",
    r"\bsuicid\b",
    r"\bheart attack\b",
    r"\bstroke\b",
    r"\bseizure\b"
]

DOSING_ADVICE_PATTERNS = [
    r"how much (should|do) i take",
    r"can i (stop|quit|discontinue) (taking|my)",
    r"should i (stop|quit|discontinue)",
    r"(double|triple|increase|decrease|lower) (my|the) dose",
    r"can you prescribe",
    r"diagnose me",
    r"what disease do i have",
    r"is this cancer",
    r"can you change my dose"
]

DISCLAIMER = "\n\n---\n*⚠️ Disclaimer: Med-Guardian provides adherence and scheduling support, not medical advice or diagnosis. Always consult your prescribing doctor or licensed pharmacist regarding medication changes or health symptoms.*"

class Guardrails:
    @staticmethod
    def pre_check(text: str) -> GuardrailResult:
        normalized = text.lower()
        
        # 1. Check for acute emergency
        for pattern in EMERGENCY_KEYWORDS:
            if re.search(pattern, normalized):
                emergency_msg = (
                    "🚨 **EMERGENCY NOTICE** 🚨\n\n"
                    "It sounds like you may be experiencing a medical emergency or severe reaction. "
                    "Med-Guardian cannot provide emergency assistance.\n\n"
                    "👉 **Please immediately call 911 (or your local emergency services number) or go to the nearest emergency room.**\n"
                    "👉 For poison emergencies in the US, contact Poison Control at **1-800-222-1222**."
                )
                return GuardrailResult(block=True, response=emergency_msg, reason="emergency")
                
        # 2. Check for out-of-scope medical/dosing advice
        for pattern in DOSING_ADVICE_PATTERNS:
            if re.search(pattern, normalized):
                advice_msg = (
                    "I cannot advise on changing, adjusting, stopping, or prescribing medications. "
                    "Med-Guardian is designed strictly for adherence tracking, dose reminders, and pharmacy organization.\n\n"
                    "Please speak directly with your prescribing physician or pharmacist before adjusting any dosages."
                ) + DISCLAIMER
                return GuardrailResult(block=True, response=advice_msg, reason="dosing_advice")
                
        return GuardrailResult(block=False)

    @staticmethod
    def post_format(text: str, add_disclaimer: bool = True) -> str:
        if not add_disclaimer:
            return text
        if "Disclaimer: Med-Guardian" in text:
            return text
        return f"{text}{DISCLAIMER}"

guardrails = Guardrails()
