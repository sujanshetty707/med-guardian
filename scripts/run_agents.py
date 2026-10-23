import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from uagents import Bureau
from core.db import init_db
from core.config import settings
from agents.orchestrator.agent import orchestrator_agent
from agents.schedule.agent import schedule_agent
from agents.safety.agent import safety_agent
from agents.pharmacy.agent import pharmacy_agent
from agents.caregiver.agent import caregiver_agent

def main():
    print("=" * 80)
    print("🚀 STARTING MED-GUARDIAN 5-AGENT BUREAU")
    print("=" * 80)
    init_db()

    endpoint_cfg = [f"http://127.0.0.1:{settings.ORCHESTRATOR_PORT}/submit"]
    bureau = Bureau(port=settings.ORCHESTRATOR_PORT, endpoint=endpoint_cfg)
    bureau.add(orchestrator_agent)
    bureau.add(schedule_agent)
    bureau.add(safety_agent)
    bureau.add(pharmacy_agent)
    bureau.add(caregiver_agent)

    print(f"✅ Orchestrator: {orchestrator_agent.address}")
    print(f"✅ Schedule:     {schedule_agent.address}")
    print(f"✅ Safety:       {safety_agent.address}")
    print(f"✅ Pharmacy:     {pharmacy_agent.address}")
    print(f"✅ Caregiver:    {caregiver_agent.address}")
    print(f"\nListening on port {settings.ORCHESTRATOR_PORT}... (Press Ctrl+C to stop)")
    bureau.run()

if __name__ == "__main__":
    main()
