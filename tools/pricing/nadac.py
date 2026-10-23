import logging
from typing import List
from core.models import Quote

logger = logging.getLogger("med-guardian.tools.pricing.nadac")

# Reference NADAC base unit costs in cents
BENCHMARK_UNIT_COSTS_CENTS = {
    "metformin": 8,       # $0.08 / tab
    "amlodipine": 6,      # $0.06 / tab
    "atorvastatin": 14,   # $0.14 / tab
    "ibuprofen": 7,       # $0.07 / tab
    "lisinopril": 9,      # $0.09 / tab
    "levothyroxine": 18,  # $0.18 / tab
    "omeprazole": 12      # $0.12 / cap
}

class NADACPriceProvider:
    name: str = "CMS NADAC Benchmark"

    async def quote(self, rxcui: str, drug_name: str, strength: str, qty: int, zip_code: str) -> List[Quote]:
        clean_name = drug_name.strip().lower().split()[0]
        unit_cost = BENCHMARK_UNIT_COSTS_CENTS.get(clean_name, 10)
        # NADAC baseline with typical dispensing fee ($2.50)
        baseline_cents = (unit_cost * qty) + 250
        
        return [
            Quote(
                provider="nadac",
                pharmacy_name="Public Reference (CMS NADAC)",
                price_cents=baseline_cents,
                currency="USD",
                estimated=True,
                delivery_days=0,
                details="National average acquisition cost reference baseline."
            )
        ]

nadac_provider = NADACPriceProvider()
