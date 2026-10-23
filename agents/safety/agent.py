import logging
from uagents import Agent, Context, Protocol
from core.config import settings
from core.models import (
    NormalizeRequest, NormalizeResponse,
    InteractionRequest, InteractionResponse
)
from tools.rxnorm import rxnorm_client
from tools.openfda import openfda_client

logger = logging.getLogger("med-guardian.agents.safety")

safety_agent = Agent(
    name="med-guardian-safety",
    seed=settings.SAFETY_SEED,
    port=settings.SAFETY_PORT,
    endpoint=[f"http://127.0.0.1:{settings.SAFETY_PORT}/submit"],
)

safety_proto = Protocol(name="SafetyProtocol", version="0.1.0")

@safety_proto.on_message(model=NormalizeRequest, replies=NormalizeResponse)
async def handle_normalize(ctx: Context, sender: str, msg: NormalizeRequest):
    ctx.logger.info(f"Normalizing {len(msg.raw_names)} drug terms for session {msg.session_id}")
    items = await rxnorm_client.normalize_list(msg.raw_names)
    unresolved = [term for term in msg.raw_names if not any(item.raw_name.lower() == term.lower() for item in items)]
    
    await ctx.send(sender, NormalizeResponse(
        session_id=msg.session_id,
        items=items,
        unresolved=unresolved
    ))

@safety_proto.on_message(model=InteractionRequest, replies=InteractionResponse)
async def handle_interactions(ctx: Context, sender: str, msg: InteractionRequest):
    ctx.logger.info(f"Screening interactions between: {msg.drug_names} (session {msg.session_id})")
    findings, source_status = await openfda_client.screen_pairs(msg.drug_names)
    
    await ctx.send(sender, InteractionResponse(
        session_id=msg.session_id,
        findings=findings,
        source_status=source_status
    ))

safety_agent.include(safety_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Starting Safety Agent on port {settings.SAFETY_PORT} (address: {safety_agent.address})")
    safety_agent.run()
