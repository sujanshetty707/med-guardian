import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import logging
from core.db import init_db
from core.config import settings
from agents.orchestrator.agent import process_orchestrator_turn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("med-guardian.e2e_sim")

DEMO_SENDER = "agent1q0v6w47573medguardiansimulator001"

async def run_e2e_simulation():
    print("=" * 80)
    print("🚀 MED-GUARDIAN END-TO-END ASI:ONE CHAT SIMULATION")
    print("=" * 80)
    init_db()

    # Step 1: Initial Medication Intake
    step1_user = "I'm managing my dad's medicines. Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin."
    print(f"\n[USER]: {step1_user}\n")
    card1 = await process_orchestrator_turn(DEMO_SENDER, step1_user)
    print(f"[MED-GUARDIAN (Card 1: Medication Intake)]:\n{card1.text_fallback}")

    # Step 2: Confirmation
    step2_user = "Confirm"
    print(f"\n[USER]: {step2_user}\n")
    card2 = await process_orchestrator_turn(DEMO_SENDER, step2_user)
    print(f"[MED-GUARDIAN]:\n{card2.text_fallback}")

    # Step 3: Add new drug that triggers Safety interaction warning
    step3_user = "Add ibuprofen 400mg as needed."
    print(f"\n[USER]: {step3_user}\n")
    card3 = await process_orchestrator_turn(DEMO_SENDER, step3_user)
    print(f"[MED-GUARDIAN (Card 2: Safety Interaction Warning)]:\n{card3.text_fallback}")

    # Step 4: Dose confirmation
    step4_user = "Taken"
    print(f"\n[USER]: {step4_user}\n")
    card4 = await process_orchestrator_turn(DEMO_SENDER, step4_user)
    print(f"[MED-GUARDIAN]:\n{card4.text_fallback}")

    # Step 5: Refill request & Price comparison carousel
    step5_user = "Refill Metformin"
    print(f"\n[USER]: {step5_user}\n")
    card5 = await process_orchestrator_turn(DEMO_SENDER, step5_user)
    print(f"[MED-GUARDIAN (Card 4: Pharmacy Price Carousel)]:\n{card5.text_fallback}")

    # Step 6: Select pharmacy option
    step6_user = "Select Option 1"
    print(f"\n[USER]: {step6_user}\n")
    card6 = await process_orchestrator_turn(DEMO_SENDER, step6_user)
    print(f"[MED-GUARDIAN (Card 5: Refill Approval & Payment Protocol)]:\n{card6.text_fallback}")

    # Step 7: Approve & Pay
    step7_user = "Approve & Pay"
    print(f"\n[USER]: {step7_user}\n")
    card7 = await process_orchestrator_turn(DEMO_SENDER, step7_user)
    print(f"[MED-GUARDIAN (Order Placed)]:\n{card7.text_fallback}")

    # Step 8: Weekly adherence report
    step8_user = "How did Dad do this week?"
    print(f"\n[USER]: {step8_user}\n")
    card8 = await process_orchestrator_turn(DEMO_SENDER, step8_user)
    print(f"[MED-GUARDIAN (Weekly Report)]:\n{card8.text_fallback}")

    # Step 9: Injected Failure Demo (Reliability recovery)
    print("\n" + "-" * 50)
    print("⚡ DEMO: INJECTED FAILURE RECOVERY (FAULT_INJECT=pricing_timeout)")
    print("-" * 50)
    settings.FAULT_INJECT = "pricing_timeout"
    card9 = await process_orchestrator_turn(DEMO_SENDER, "Refill Metformin")
    print(f"[MED-GUARDIAN (Graceful Degraded Fallback)]:\n{card9.text_fallback}")
    settings.FAULT_INJECT = ""

    # Step 10: Safety Guardrail test (Emergency detection)
    print("\n" + "-" * 50)
    print("🚨 DEMO: SAFETY GUARDRAIL (EMERGENCY DETECTION)")
    print("-" * 50)
    card10 = await process_orchestrator_turn(DEMO_SENDER, "My dad has chest pain and can't breathe!")
    print(f"[MED-GUARDIAN (Emergency Action)]:\n{card10.text_fallback}")

    print("\n" + "=" * 80)
    print("🎉 ALL SIMULATION STEPS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_e2e_simulation())
