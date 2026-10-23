import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import uuid
from datetime import datetime, timezone
from core.db import init_db, SessionLocal, Patient, CaregiverLink, Medication, Schedule, DoseEvent

def seed():
    print("🌱 Seeding Med-Guardian Demo Data...")
    init_db()

    with SessionLocal() as db:
        # Check if demo patient exists
        pat = db.query(Patient).filter(Patient.display_name == "Dad (Ramesh)").first()
        if not pat:
            pat = Patient(
                id="pat_ramesh_001",
                display_name="Dad (Ramesh)",
                tz="America/New_York"
            )
            db.add(pat)
            db.commit()
            print(f"✅ Created Patient: {pat.display_name} ({pat.id})")

        # Caregiver Link (Priya)
        link = db.query(CaregiverLink).filter(CaregiverLink.patient_id == pat.id).first()
        if not link:
            link = CaregiverLink(
                id="lnk_priya_001",
                patient_id=pat.id,
                caregiver_name="Priya (Daughter)",
                caregiver_contact="@priya_caregiver_demo",
                channel="telegram",
                consent_at=datetime.now(timezone.utc)
            )
            db.add(link)
            db.commit()
            print(f"✅ Linked Caregiver: {link.caregiver_name} with recorded patient consent.")

        print("✨ Database seed complete!")

if __name__ == "__main__":
    seed()
