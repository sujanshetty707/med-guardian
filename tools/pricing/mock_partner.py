import asyncio
import logging
from typing import List
from core.models import Quote
from core.resilience import (
    check_fault_injection, pricing_circuit_breaker, CircuitBreakerOpenException
)

logger = logging.getLogger("med-guardian.tools.pricing.mock_partner")

# Base retail prices (in cents) for a 30-day supply
BASE_RETAIL_CENTS = {
    "metformin": 1200,     # $12.00
    "amlodipine": 1050,    # $10.50
    "atorvastatin": 1650,  # $16.50
    "ibuprofen": 850,      # $8.50
    "lisinopril": 1100,    # $11.00
    "levothyroxine": 1900, # $19.00
    "omeprazole": 1400     # $14.00
}

class MockPartnerPriceProvider:
    name: str = "Partner Network"

    async def quote(self, rxcui: str, drug_name: str, strength: str, qty: int, zip_code: str) -> List[Quote]:
        # Check circuit breaker
        if not pricing_circuit_breaker.allow_request():
            raise CircuitBreakerOpenException("Pricing circuit breaker is OPEN due to repeated partner timeouts.")

        try:
            # Check for demo fault injection (e.g. FAULT_INJECT=pricing_timeout)
            check_fault_injection("pricing")
            
            clean_name = drug_name.strip().lower().split()[0]
            base_30 = BASE_RETAIL_CENTS.get(clean_name, 1200)
            ratio = qty / 30.0

            # 3 competitive partner pharmacy quotes
            quotes = [
                Quote(
                    provider="mock_partner",
                    pharmacy_name="Costco Pharmacy (Direct Mail)",
                    price_cents=int(base_30 * ratio * 0.65),  # 35% discount
                    currency="USD",
                    estimated=False,
                    delivery_days=2,
                    details="Free standard shipping. Lowest cost member price."
                ),
                Quote(
                    provider="mock_partner",
                    pharmacy_name="CVS Health (Local Pickup)",
                    price_cents=int(base_30 * ratio * 0.90),  # 10% discount
                    currency="USD",
                    estimated=False,
                    delivery_days=0,
                    details="Ready in 1 hour at your neighborhood CVS store."
                ),
                Quote(
                    provider="mock_partner",
                    pharmacy_name="Walgreens Pharmacy (Drive-thru)",
                    price_cents=int(base_30 * ratio * 0.85),  # 15% discount
                    currency="USD",
                    estimated=False,
                    delivery_days=0,
                    details="Drive-thru express pickup with Rewards savings."
                )
            ]
            
            pricing_circuit_breaker.record_success()
            return sorted(quotes, key=lambda q: q.price_cents)

        except Exception as e:
            pricing_circuit_breaker.record_failure()
            logger.warning(f"Mock partner quote generation failed: {e}")
            raise e

mock_partner_provider = MockPartnerPriceProvider()
