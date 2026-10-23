import pytest
from tools.rxnorm import rxnorm_client
from tools.openfda import openfda_client

@pytest.mark.asyncio
async def test_rxnorm_normalization():
    drug = await rxnorm_client.normalize_term("Metformin 500mg")
    assert drug is not None
    assert drug.rxcui == "6809"
    assert "Metformin" in drug.name

@pytest.mark.asyncio
async def test_openfda_interaction_screening_flagged():
    # Metformin + Ibuprofen has an FDA label interaction note
    findings, status = await openfda_client.screen_pairs(["Metformin", "Ibuprofen"])
    assert len(findings) >= 1
    f = findings[0]
    assert "Ibuprofen" in (f.drug_a, f.drug_b)
    assert "Metformin" in (f.drug_a, f.drug_b)
    assert "lactic acidosis" in f.finding.lower() or "renal" in f.finding.lower()
    assert "?" in f.pharmacist_question  # Phrased as a question for pharmacist
    assert "FDA" in f.source

@pytest.mark.asyncio
async def test_openfda_interaction_no_flags():
    # Vitamins / non-interacting pair in catalog
    findings, status = await openfda_client.screen_pairs(["Omeprazole"])
    assert len(findings) == 0
