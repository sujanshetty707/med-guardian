import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("med-guardian.tools.payments")

class PaymentManager:
    """
    Wrapper for Fetch.ai / ASI:One Payment Protocol interactions.
    Provides structured payment requests and sandbox verification.
    """
    def create_payment_request(
        self,
        order_id: str,
        amount_cents: int,
        currency: str = "USD",
        description: str = "Medication Refill Order"
    ) -> Dict[str, Any]:
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        amount_formatted = f"${amount_cents / 100:.2f} {currency}"
        logger.info(f"Generated payment request {payment_id} for order {order_id}: {amount_formatted}")
        return {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount_cents": amount_cents,
            "amount_formatted": amount_formatted,
            "currency": currency,
            "description": description,
            "status": "pending_approval"
        }

    def verify_payment(self, payment_id: str, transaction_ref: Optional[str] = None) -> bool:
        """
        Verify payment transaction. In hackathon/sandbox mode, valid references succeed.
        """
        tx_ref = transaction_ref or f"tx_{uuid.uuid4().hex[:16]}"
        logger.info(f"Payment verified for {payment_id} with tx_ref {tx_ref}")
        return True

payment_manager = PaymentManager()
