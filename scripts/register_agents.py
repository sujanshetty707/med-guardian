import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents.orchestrator.agent import orchestrator_agent
from agents.schedule.agent import schedule_agent
from agents.safety.agent import safety_agent
from agents.pharmacy.agent import pharmacy_agent
from agents.caregiver.agent import caregiver_agent

AGENTS_METADATA = [
    {
        "agent": orchestrator_agent,
        "name": "Med-Guardian Orchestrator",
        "handle": "med-guardian",
        "description": "ASI:One-native medication adherence, dose tracking, price comparison, and caregiver alert system.",
        "keywords": ["medication", "reminder", "refill", "caregiver", "pharmacy", "adherence", "drug-interaction"],
        "readme": (
            "## Med-Guardian\n"
            "An autonomous multi-agent health adherence assistant designed for ASI:One.\n\n"
            "### Example Prompts:\n"
            "1. \"I'm managing my dad's medicines: Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin.\"\n"
            "2. \"Add ibuprofen 400mg as needed.\"\n"
            "3. \"Refill Metformin\"\n"
            "4. \"How did Dad do this week?\"\n"
        )
    },
    {
        "agent": schedule_agent,
        "name": "Med-Guardian Schedule & Adherence",
        "handle": "med-guardian-schedule",
        "description": "Dose scheduler, reminder coordinator, runway calculator, and missed-dose detection agent.",
        "keywords": ["schedule", "dose", "adherence", "runway", "timer"],
        "readme": "Specialist agent maintaining medication schedule state machines and calculating refill runways."
    },
    {
        "agent": safety_agent,
        "name": "Med-Guardian Safety",
        "handle": "med-guardian-safety",
        "description": "RxNorm drug normalization and openFDA drug label interaction screening agent.",
        "keywords": ["safety", "rxnorm", "openfda", "interactions", "fda-label"],
        "readme": "Screens medication combinations against FDA label drug-interaction sections and generates pharmacist questions."
    },
    {
        "agent": pharmacy_agent,
        "name": "Med-Guardian Pharmacy & Pricing",
        "handle": "med-guardian-pharmacy",
        "description": "Multi-provider pharmacy price comparison and Payment Protocol refill checkout agent.",
        "keywords": ["pharmacy", "pricing", "refill", "payment-protocol", "nadac"],
        "readme": "Compares pharmacy pricing across partners and CMS benchmarks with Payment Protocol checkout."
    },
    {
        "agent": caregiver_agent,
        "name": "Med-Guardian Caregiver Alert",
        "handle": "med-guardian-caregiver",
        "description": "Caregiver escalation, missed-dose alerting, and family adherence reporting agent.",
        "keywords": ["caregiver", "escalation", "telegram", "sms", "alert"],
        "readme": "Dispatches alerts to remote family caregivers when scheduled doses are missed past the grace window."
    }
]

def print_registration_details():
    print("=" * 80)
    print("📋 MED-GUARDIAN AGENTVERSE REGISTRATION GUIDE")
    print("=" * 80)
    print("To register these agents on Fetch.ai Agentverse:")
    print("1. Set `mailbox=True` on the agent or run them with mailbox connectivity.")
    print("2. Connect your Agentverse account to register their addresses.")
    print("3. Fill in the profile pages with the metadata below:\n")

    for item in AGENTS_METADATA:
        ag = item["agent"]
        print(f"🔹 **{item['name']}**")
        print(f"   • Address:  `{ag.address}`")
        print(f"   • Handle:   `{item['handle']}`")
        print(f"   • Keywords: {', '.join(item['keywords'])}")
        print(f"   • Description: {item['description']}")
        print(f"   • Protocol: Agent Chat Protocol (ACP) + Custom Pydantic Models")
        print("-" * 80)

if __name__ == "__main__":
    print_registration_details()
