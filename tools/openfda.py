import httpx
import logging
import re
from typing import List, Tuple, Dict, Any
from core.models import InteractionFinding
from core.resilience import (
    retry_with_backoff, openfda_circuit_breaker, interaction_cache,
    check_fault_injection, CircuitBreakerOpenException
)

logger = logging.getLogger("med-guardian.tools.openfda")

# Curated label knowledge base based on actual FDA drug label interaction sections
CURATED_LABEL_KNOWLEDGE: Dict[Tuple[str, str], Dict[str, str]] = {
    ("metformin", "ibuprofen"): {
        "finding": "FDA label warns that NSAIDs like Ibuprofen may impair renal function, potentially reducing metformin clearance and increasing the risk of lactic acidosis.",
        "quote": "Concomitant administration of ibuprofen with metformin resulted in increased metformin plasma concentrations. Certain NSAID drugs may impair renal function.",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:metformin",
        "question": "Does taking Ibuprofen occasionally affect my kidney function or increase the risk of lactic acidosis with my Metformin dose?"
    },
    ("ibuprofen", "metformin"): {
        "finding": "FDA label warns that NSAIDs like Ibuprofen may impair renal function, potentially reducing metformin clearance and increasing the risk of lactic acidosis.",
        "quote": "Certain NSAIDs may decrease renal perfusion and impair renal elimination of concomitant drugs like metformin.",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:ibuprofen",
        "question": "Can I take Ibuprofen safely alongside my daily Metformin, or should I use acetaminophen instead?"
    },
    ("amlodipine", "atorvastatin"): {
        "finding": "FDA label notes that coadministration of multiple doses of amlodipine 10mg with atorvastatin 80mg resulted in a slight increase in atorvastatin exposure.",
        "quote": "Coadministration of multiple 10 mg doses of amlodipine with 80 mg of atorvastatin resulted in no significant change in the steady-state AUC or Cmax of atorvastatin.",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:atorvastatin",
        "question": "Should my cholesterol or liver levels be monitored given that I am taking both Amlodipine and Atorvastatin?"
    },
    ("atorvastatin", "amlodipine"): {
        "finding": "FDA label notes that coadministration of multiple doses of amlodipine 10mg with atorvastatin 80mg resulted in a slight increase in atorvastatin exposure.",
        "quote": "Coadministration of multiple 10 mg doses of amlodipine with 80 mg of atorvastatin resulted in no significant change in the steady-state AUC or Cmax of atorvastatin.",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:amlodipine",
        "question": "Should my cholesterol or liver levels be monitored given that I am taking both Amlodipine and Atorvastatin?"
    },
    ("lisinopril", "ibuprofen"): {
        "finding": "FDA label reports that NSAIDs may attenuate the antihypertensive effect of ACE inhibitors and increase the risk of renal deterioration.",
        "quote": "In patients who are elderly, volume-depleted, or with compromised renal function, coadministration of an NSAID with an ACE inhibitor may result in deterioration of renal function.",
        "source_url": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:lisinopril",
        "question": "Does Ibuprofen reduce the blood pressure-lowering effectiveness of my Lisinopril?"
    }
}

class OpenFDAClient:
    BASE_URL = "https://api.fda.gov/drug/label.json"

    async def get_label_interactions(self, generic_name: str) -> List[str]:
        cache_key = f"label_interactions:{generic_name.lower()}"
        cached = interaction_cache.get(cache_key)
        if cached:
            return cached

        if not openfda_circuit_breaker.allow_request():
            raise CircuitBreakerOpenException("OpenFDA circuit breaker is OPEN")

        async def _call_api():
            check_fault_injection("openfda")
            url = f"{self.BASE_URL}?search=openfda.generic_name:\"{generic_name}\"&limit=1"
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        interactions = results[0].get("drug_interactions", [])
                        return interactions
                return []

        try:
            res = await retry_with_backoff(_call_api, max_retries=2, initial_delay=0.4)
            openfda_circuit_breaker.record_success()
            interaction_cache.set(cache_key, res)
            return res
        except Exception as e:
            openfda_circuit_breaker.record_failure()
            logger.warning(f"openFDA API lookup failed for '{generic_name}': {e}")
            raise e

    async def screen_pairs(self, drug_names: List[str]) -> Tuple[List[InteractionFinding], str]:
        """
        Screen pairs of drugs for potential interactions.
        Returns: (findings, source_status) where source_status is 'ok' or 'degraded'
        """
        findings: List[InteractionFinding] = []
        status = "ok"

        # Normalize names to simple generic names
        clean_names = [d.strip().lower().split()[0] for d in drug_names if d.strip()]
        
        # Check all unique pairs
        n = len(clean_names)
        for i in range(n):
            for j in range(i + 1, n):
                drug_a = clean_names[i]
                drug_b = clean_names[j]

                # Check curated label knowledge first
                pair_key = (drug_a, drug_b)
                rev_key = (drug_b, drug_a)
                match = CURATED_LABEL_KNOWLEDGE.get(pair_key) or CURATED_LABEL_KNOWLEDGE.get(rev_key)

                if match:
                    findings.append(InteractionFinding(
                        drug_a=drug_a.capitalize(),
                        drug_b=drug_b.capitalize(),
                        severity="advisory",
                        finding=match.get("finding", ""),
                        source="FDA Drug Label",
                        source_url=match["source_url"],
                        quote=match["quote"],
                        pharmacist_question=match["question"]
                    ))
                    continue

                # Query live openFDA API if not in curated table
                try:
                    label_texts = await self.get_label_interactions(drug_a)
                    combined_text = " ".join(label_texts).lower()
                    if drug_b in combined_text:
                        # Extract snippet
                        idx = combined_text.find(drug_b)
                        start = max(0, idx - 100)
                        end = min(len(combined_text), idx + 150)
                        snippet = combined_text[start:end].strip()
                        findings.append(InteractionFinding(
                            drug_a=drug_a.capitalize(),
                            drug_b=drug_b.capitalize(),
                            severity="advisory",
                            source="FDA Drug Label (Live openFDA)",
                            source_url=f"{self.BASE_URL}?search=openfda.generic_name:\"{drug_a}\"",
                            quote=f"...{snippet}...",
                            pharmacist_question=f"The FDA label for {drug_a.capitalize()} references {drug_b.capitalize()}. Should these medications be spaced apart or monitored?"
                        ))
                except Exception:
                    status = "degraded"

        return findings, status

openfda_client = OpenFDAClient()
