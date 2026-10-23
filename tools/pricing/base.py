from typing import List, Protocol
from core.models import Quote

class PriceProvider(Protocol):
    name: str
    async def quote(self, rxcui: str, drug_name: str, strength: str, qty: int, zip_code: str) -> List[Quote]:
        ...
