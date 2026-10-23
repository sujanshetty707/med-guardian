import pytest
import asyncio
from core.config import settings
from core.resilience import (
    pricing_circuit_breaker, openfda_circuit_breaker, CircuitBreakerOpenException
)
from tools.pricing.mock_partner import mock_partner_provider
from tools.pricing.nadac import nadac_provider
from agents.orchestrator.agent import process_orchestrator_turn

@pytest.mark.asyncio
async def test_pricing_fault_injection_and_fallback():
    # Set fault injection for pricing
    original_fault = settings.FAULT_INJECT
    settings.FAULT_INJECT = "pricing_timeout"
    
    try:
        # Calling mock partner directly should raise timeout error
        with pytest.raises((asyncio.TimeoutError, ConnectionError, CircuitBreakerOpenException)):
            await mock_partner_provider.quote("6809", "Metformin", "500mg", 30, "94016")

        # But the orchestrator process_orchestrator_turn handles it and gracefully falls back to estimates!
        card_payload = await process_orchestrator_turn("test_sender_fail", "Refill Metformin")
        
        # Verify fallback response exists and notes that quotes are estimates
        assert card_payload is not None
        assert "Costco Pharmacy" in card_payload.text_fallback
        assert "estimate" in card_payload.text_fallback.lower()
    finally:
        settings.FAULT_INJECT = original_fault
        pricing_circuit_breaker.record_success()

@pytest.mark.asyncio
async def test_circuit_breaker_tripping():
    cb = pricing_circuit_breaker
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.allow_request() is False
    # Reset
    cb.record_success()
    assert cb.state == "CLOSED"
