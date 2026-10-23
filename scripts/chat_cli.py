import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from core.db import init_db
from agents.orchestrator.agent import process_orchestrator_turn

CLI_SENDER = "agent1q_local_interactive_chat_user"

async def chat_loop():
    init_db()
    print("=" * 80)
    print("💬 MED-GUARDIAN INTERACTIVE CHAT (Local Console)")
    print("=" * 80)
    print("Type your message below to chat with Med-Guardian in real-time.")
    print("Type 'exit' or 'quit' to end.\n")

    # Welcome message
    welcome = await process_orchestrator_turn(CLI_SENDER, "hello")
    print(f"Med-Guardian:\n{welcome.text_fallback}\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Ending chat. Goodbye!")
                break

            print("\nThinking...")
            reply = await process_orchestrator_turn(CLI_SENDER, user_input)
            print(f"\nMed-Guardian:\n{reply.text_fallback}\n")
            print("-" * 60)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    asyncio.run(chat_loop())
