from datetime import datetime
from typing import List, Optional, Tuple
from uagents import Model

# --- Drug Normalization ---
class NormalizedDrug(Model):
    raw_name: str
    rxcui: str
    name: str
    strength: str = ""
    dosage_form: str = ""
    confidence: float = 1.0

class NormalizeRequest(Model):
    session_id: str
    raw_names: List[str]

class NormalizeResponse(Model):
    session_id: str
    items: List[NormalizedDrug]
    unresolved: List[str]

# --- Interaction Screening ---
class InteractionFinding(Model):
    drug_a: str
    drug_b: str
    severity: str = "warning"
    finding: str = ""
    source: str = "openFDA Drug Label"
    source_url: str = ""
    quote: str = ""
    pharmacist_question: str

class InteractionRequest(Model):
    session_id: str
    rxcuis: List[str]
    drug_names: List[str] = []

class InteractionResponse(Model):
    session_id: str
    findings: List[InteractionFinding]
    source_status: str  # "ok" | "degraded" | "error"

# --- Pharmacy & Pricing ---
class Quote(Model):
    provider: str
    pharmacy_name: str
    price_cents: int
    currency: str = "USD"
    estimated: bool = True
    delivery_days: int = 1
    details: str = ""

    @property
    def price_dollars(self) -> float:
        return round(self.price_cents / 100.0, 2)

class PriceRequest(Model):
    session_id: str
    rxcui: str
    drug_name: str
    strength: str = ""
    qty: int = 30
    zip_code: str = "94016"

class PriceResponse(Model):
    session_id: str
    quotes: List[Quote]
    is_estimate: bool = True
    error: Optional[str] = None

class RefillOrderRequest(Model):
    session_id: str
    patient_id: str
    medication_id: str
    drug_name: str
    pharmacy_name: str
    quote_cents: int
    payment_ref: str = ""

class RefillOrderResponse(Model):
    session_id: str
    order_id: str
    status: str  # "placed", "failed"
    message: str

# --- Scheduling & Adherence ---
class ParsedMedSchedule(Model):
    drug_name: str
    rxcui: str = ""
    strength: str = ""
    frequency: str = "daily"
    times: List[str] = ["08:00"]
    qty_on_hand: int = 30
    qty_per_dose: int = 1
    instructions: str = ""

class SaveMedicationsRequest(Model):
    session_id: str
    patient_id: str
    medications: List[ParsedMedSchedule]

class SaveMedicationsResponse(Model):
    session_id: str
    success: bool
    saved_count: int
    message: str

class LogDoseRequest(Model):
    session_id: str
    patient_id: str
    medication_name: str
    action: str  # "taken" | "skipped" | "later"
    channel: str = "asi_one"

class LogDoseResponse(Model):
    session_id: str
    success: bool
    message: str
    dose_event_id: Optional[str] = None

class RunwayItem(Model):
    medication_id: str
    medication_name: str
    rxcui: str
    strength: str
    qty_on_hand: int
    days_left: int
    needs_refill: bool

class RunwayCheckRequest(Model):
    session_id: str
    patient_id: str

class RunwayCheckResponse(Model):
    session_id: str
    items: List[RunwayItem]

class AdherenceReportRequest(Model):
    session_id: str
    patient_id: str
    days: int = 7

class AdherenceReportResponse(Model):
    session_id: str
    patient_name: str
    adherence_rate: float
    taken_count: int
    skipped_count: int
    missed_count: int
    summary: str

# --- Caregiver Escalation ---
class MissedDoseEvent(Model):
    patient_id: str
    patient_name: str
    med_name: str
    strength: str
    due_at_iso: str
    attempts: int
    caregiver_channel: str = "telegram"

class CaregiverAlertResponse(Model):
    event_id: str
    dispatched: bool
    channel: str
    message: str

class LinkCaregiverRequest(Model):
    session_id: str
    patient_id: str
    caregiver_name: str
    contact_info: str
    channel: str = "telegram"

class LinkCaregiverResponse(Model):
    session_id: str
    success: bool
    link_id: str
    message: str
