import logging
import uuid
from uagents import Agent, Context, Protocol
from core.config import settings
from core.models import (
    PriceRequest, PriceResponse, RefillOrderRequest, RefillOrderResponse, Quote
)
from core.db import SessionLocal, RefillOrder
from tools.pricing.mock_partner import mock_partner_provider
from tools.pricing.nadac import nadac_provider
from tools.payments import payment_manager

logger = logging.getLogger("med-guardian.agents.pharmacy")

pharmacy_agent = Agent(
    name="med-guardian-pharmacy",
    seed=settings.PHARMACY_SEED,
    port=settings.PHARMACY_PORT,
    endpoint=[f"http://127.0.0.1:{settings.PHARMACY_PORT}/submit"],
)

pharmacy_proto = Protocol(name="PharmacyProtocol", version="0.1.0")

@pharmacy_proto.on_message(model=PriceRequest, replies=PriceResponse)
async def handle_pricing(ctx: Context, sender: str, msg: PriceRequest):
    ctx.logger.info(f"Gathering pharmacy prices for {msg.drug_name} {msg.strength} (session {msg.session_id})")
    quotes = []
    is_estimate = False
    error_msg = None

    # 1. Try Partner Network
    try:
        partner_quotes = await mock_partner_provider.quote(
            rxcui=msg.rxcui,
            drug_name=msg.drug_name,
            strength=msg.strength,
            qty=msg.qty,
            zip_code=msg.zip_code
        )
        quotes.extend(partner_quotes)
    except Exception as e:
        ctx.logger.warning(f"Partner price lookup failed ({type(e).__name__}: {e}). Tripping fallback to reference pricing.")
        is_estimate = True
        error_msg = str(e)
        
        # 2. Resilient Fallback to CMS NADAC Benchmark
        try:
            nadac_quotes = await nadac_provider.quote(
                rxcui=msg.rxcui,
                drug_name=msg.drug_name,
                strength=msg.strength,
                qty=msg.qty,
                zip_code=msg.zip_code
            )
            # Create synthetic estimated quotes based on baseline
            base_q = nadac_quotes[0]
            quotes = [
                Quote(
                    provider="nadac_fallback",
                    pharmacy_name="Costco Pharmacy (Est. Quote)",
                    price_cents=int(base_q.price_cents * 1.1),
                    currency="USD",
                    estimated=True,
                    delivery_days=2,
                    details="Estimated quote based on CMS acquisition benchmarks."
                ),
                Quote(
                    provider="nadac_fallback",
                    pharmacy_name="Community Pharmacy (Est. Quote)",
                    price_cents=int(base_q.price_cents * 1.3),
                    currency="USD",
                    estimated=True,
                    delivery_days=0,
                    details="Estimated local pharmacy benchmark quote."
                )
            ]
        except Exception as fallback_err:
            ctx.logger.error(f"Fallback pricing also failed: {fallback_err}")

    await ctx.send(sender, PriceResponse(
        session_id=msg.session_id,
        quotes=quotes,
        is_estimate=is_estimate,
        error=error_msg
    ))

@pharmacy_proto.on_message(model=RefillOrderRequest, replies=RefillOrderResponse)
async def handle_refill_order(ctx: Context, sender: str, msg: RefillOrderRequest):
    ctx.logger.info(f"Processing refill order for {msg.drug_name} at {msg.pharmacy_name} (session {msg.session_id})")
    
    # Verify payment reference
    is_paid = payment_manager.verify_payment(msg.payment_ref)
    order_id = f"ord_{uuid.uuid4().hex[:8]}"

    if is_paid:
        # Persist order in DB
        with SessionLocal() as db:
            order = RefillOrder(
                id=order_id,
                medication_id=msg.medication_id or "demo_med",
                provider=msg.pharmacy_name,
                quote_cents=msg.quote_cents,
                status="placed",
                payment_ref=msg.payment_ref
            )
            db.add(order)
            db.commit()

        await ctx.send(sender, RefillOrderResponse(
            session_id=msg.session_id,
            order_id=order_id,
            status="placed",
            message=f"Order successfully placed with {msg.pharmacy_name}. Ready for pickup or delivery."
        ))
    else:
        await ctx.send(sender, RefillOrderResponse(
            session_id=msg.session_id,
            order_id=order_id,
            status="failed",
            message="Payment verification was unsuccessful. Order was not submitted."
        ))

pharmacy_agent.include(pharmacy_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"Starting Pharmacy Agent on port {settings.PHARMACY_PORT} (address: {pharmacy_agent.address})")
    pharmacy_agent.run()
