import pytest
from datetime import datetime, timezone
from core.models import MissedDoseEvent
from tools.notify.dispatcher import dispatcher
from core.db import SessionLocal, init_db, Patient, Medication, DoseEvent

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

@pytest.mark.asyncio
async def test_caregiver_alert_dispatch():
    dispatched = await dispatcher.dispatch_caregiver_alert(
        caregiver_name="Priya",
        patient_name="Ramesh",
        medication_name="Metformin",
        strength="500mg",
        due_time="08:00 AM",
        channel="telegram",
        channel_addr="12345678"
    )
    assert dispatched is True

@pytest.mark.asyncio
async def test_dose_log_and_adherence_calc():
    with SessionLocal() as db:
        patient = Patient(id="test_pat_1", display_name="Test Ramesh")
        db.merge(patient)
        
        med = Medication(
            id="test_med_1",
            patient_id="test_pat_1",
            display_name="Metformin",
            strength="500mg",
            qty_on_hand=30
        )
        db.merge(med)

        # Record taken dose
        now = datetime.now(timezone.utc)
        dose = DoseEvent(
            id="test_dose_1",
            medication_id="test_med_1",
            due_at=now,
            status="taken",
            confirmed_at=now
        )
        db.merge(dose)
        db.commit()

        # Query events
        events = db.query(DoseEvent).filter(DoseEvent.medication_id == "test_med_1").all()
        taken = sum(1 for e in events if e.status == "taken")
        assert taken == 1
