import pytest
from core.llm import llm_parser
from core.guardrails import guardrails

@pytest.mark.asyncio
async def test_medication_parsing_complex():
    text = "I'm managing my dad's medicines. Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin."
    intent = await llm_parser.classify_and_extract(text, {})
    assert intent.name == "ADD_MEDICATIONS"
    meds = intent.entities.get("medications", [])
    assert len(meds) >= 3
    
    names = [m.drug_name.lower() for m in meds]
    assert "metformin" in names
    assert "amlodipine" in names
    assert "atorvastatin" in names

    # Check strengths and frequencies
    met = next(m for m in meds if m.drug_name.lower() == "metformin")
    assert "500" in met.strength
    assert "twice" in met.frequency
    assert len(met.times) == 2
    assert met.qty_on_hand == 20  # 10 days * 2 doses/day

    aml = next(m for m in meds if m.drug_name.lower() == "amlodipine")
    assert "5" in aml.strength
    assert len(aml.times) == 1

@pytest.mark.asyncio
async def test_add_as_needed_medication():
    text = "Add ibuprofen 400mg as needed."
    intent = await llm_parser.classify_and_extract(text, {})
    assert intent.name == "ADD_MEDICATIONS"
    meds = intent.entities.get("medications", [])
    assert len(meds) == 1
    ib = meds[0]
    assert ib.drug_name.lower() == "ibuprofen"
    assert "400" in ib.strength
    assert "needed" in ib.frequency

@pytest.mark.asyncio
async def test_guardrail_emergency_detection():
    emergency_text = "Help, my dad had an overdose and has severe chest pain!"
    res = guardrails.pre_check(emergency_text)
    assert res.block is True
    assert res.reason == "emergency"
    assert "EMERGENCY NOTICE" in res.response
    assert "911" in res.response

@pytest.mark.asyncio
async def test_guardrail_dosing_advice_decline():
    advice_text = "Can I stop taking Metformin or double my dose?"
    res = guardrails.pre_check(advice_text)
    assert res.block is True
    assert res.reason == "dosing_advice"
    assert "cannot advise" in res.response.lower()

def test_guardrail_post_format_disclaimer():
    msg = "Here are your medication details."
    formatted = guardrails.post_format(msg)
    assert "Disclaimer: Med-Guardian" in formatted
