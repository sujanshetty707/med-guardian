import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

def run():
    print("Calling register_chat_agent with Agentverse...")
    agentverse_key = os.environ.get("AGENTVERSE_KEY")
    agent_seed = os.environ.get("AGENT_SEED_PHRASE", "med-guardian-orchestrator-seed-2026-secure")

    if not agentverse_key:
        print("ERROR: AGENTVERSE_KEY environment variable not set!")
        return

    endpoint_url = "https://movie-joseph-descriptions-speaking.trycloudflare.com/submit"
    print(f"Registering Med-Guardian at {endpoint_url}...")

    try:
        res = register_chat_agent(
            "Med-Guardian",
            endpoint_url,
            active=True,
            credentials=RegistrationRequestCredentials(
                agentverse_api_key=agentverse_key,
                agent_seed_phrase=agent_seed,
            ),
        )
        print("Registration result:", res)
        print("SUCCESS! Med-Guardian is now registered with Agentverse.")
    except Exception as e:
        print("Registration error:", type(e).__name__, e)

if __name__ == "__main__":
    run()
