# Med-Guardian 🛡️💊

**An ASI:One-Native Medication Adherence, Refill, and Caregiver-Alert Multi-Agent System**

Built with **Fetch.ai uAgents**, registered on **Agentverse**, discoverable via **ASI:One**, and engineered in **Google Antigravity**.

---

## 1. Problem & Vision

- **The Problem:** Half of all chronic patients do not take their medications as prescribed. Elderly parents managing polypharmacy (3–8 daily pills) face dangerous drug interactions, missed doses, and refill gaps. Adult children caring for them remotely have no lightweight way to know if Mom or Dad took their morning doses or if refills are running low.
- **The Vision:** One seamless conversation in **ASI:One** replaces a messy combination of pill-reminder apps, pharmacy portals, drug websites, and frantic phone calls.
- **Scope Limit & Safety by Design:** Med-Guardian provides **adherence support and organization**, not diagnosis or medical advice. Drug interaction checks cite official FDA label data and frame actionable questions to ask a licensed pharmacist or prescribing physician.

---

## 2. Multi-Agent Architecture

```
                    ┌─────────────────────────────┐
                    │          ASI:One            │
                    │  (chat + Interactive Cards) │
                    └──────────────┬──────────────┘
                                   │ Agent Chat Protocol (ACP)
                                   ▼
┌───────────────────────────────────────────────────────────────┐
│                     Agentverse (Registry & Mailbox)           │
│                                                               │
│   ┌─────────────────────────────────────────────────────┐     │
│   │  1. GUARDIAN ORCHESTRATOR  (ASI:One-facing)         │     │
│   │     intent parsing · planning · session state       │     │
│   └──┬──────────┬───────────┬────────────┬──────────────┘     │
│      │ Typed Pydantic messages (ctx.send)                     │
│      ▼          ▼           ▼            ▼                    │
│  ┌────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐         │
│  │2.SCHED-│ │3.SAFETY │ │4.PHARMACY│ │5.CAREGIVER   │         │
│  │ULE &   │ │(interac-│ │& PRICING │ │ALERT         │         │
│  │ADHERENCE│ │tion)   │ │          │ │              │         │
│  └───┬────┘ └────┬────┘ └────┬─────┘ └──────┬───────┘         │
└──────┼───────────┼───────────┼──────────────┼─────────────────┘
       ▼           ▼           ▼              ▼
   Postgres/    RxNorm      Price data /   Telegram / SMS /
   SQLite      openFDA     pharmacy       email gateway
               DailyMed    adapter        Payment Protocol
```

### 5 Specialized Agents

| # | Agent | Role | Port | Key Tools & Protocols |
|---|---|---|---|---|
| 1 | **Guardian Orchestrator** | Entry point; intent classification, workflow planning, interactive cards | `8000` | Agent Chat Protocol (ACP), ASI1 LLM client, Sessions |
| 2 | **Schedule & Adherence** | Parses schedules, manages dose state machine, computes refill runway | `8001` | SQLite / Postgres DB, dose logging, APScheduler |
| 3 | **Safety Agent** | Drug name normalization & FDA label drug-interaction screening | `8002` | RxNav / RxNorm API, openFDA label API, safety filters |
| 4 | **Pharmacy & Pricing** | Price comparison across pharmacies & Payment Protocol checkout | `8003` | Mock partner network, CMS NADAC baseline, Payment Protocol |
| 5 | **Caregiver Alert** | Caregiver linking, patient consent recording, missed-dose escalation | `8004` | Telegram Bot, SMS/Twilio fallback, Weekly adherence reporting |

---

## 3. Hackathon Criteria & Bonus Features

- [x] **Agent Chat Protocol (ACP):** Every agent implements ACP with instant `ChatAcknowledgement` and structured `ChatMessage`.
- [x] **Interactive Cards & Text Fallbacks:** Medication intake schedule card, drug interaction card, dose check-in card, price carousel card, and refill approval card.
- [x] **Payment Protocol:** Refill order flow generates a structured payment authorization request and records transaction references.
- [x] **Reliability & Resilience:** Circuit breakers, retry with exponential backoff & jitter, in-memory TTL caching, and graceful degradation to CMS NADAC estimates when partner APIs time out.
- [x] **Injected Fault Recovery Demo:** Set `FAULT_INJECT=pricing_timeout` to demonstrate real-time failure detection and graceful recovery on camera.
- [x] **Emergency & Scope Guardrails:** Immediate emergency guidance on acute symptoms (overdose, chest pain, anaphylaxis) with 911 / Poison Control instructions, plus non-diagnostic disclaimers on every response.

---

## 4. Quickstart Guide

### 1. Installation

```bash
# Clone the repository and navigate into it
cd "med care"

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)

Copy the template:
```bash
cp .env.example .env
```
*(Deterministic test seeds are pre-filled so the system runs immediately. Add your optional Telegram bot token, Twilio credentials, or ASI1 API key as desired).*

### 3. Seed Demo Data

```powershell
.\run.ps1 seed
# or
python scripts/seed_demo_data.py
```

### 4. Run the Full Test Suite (12 Tests)

```powershell
.\run.ps1 test
# or
pytest -v tests/
```

### 5. Run the Multi-Turn ASI:One Simulator

Run the complete multi-turn conversation reproducing the primary PRD demo flow:
```powershell
.\run.ps1 sim
# or
python tests/e2e_chat_sim.py
```

### 6. Start the 5-Agent Bureau

```powershell
.\run.ps1 run
# or
python scripts/run_agents.py
```

---

## 5. Primary Demo Flow (Prompts for ASI:One)

1. **Medication Intake:**
   > *"I'm managing my dad's medicines: Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin."*
   - Med-Guardian parses schedules, normalizes names to RxNorm, screens initial combinations, and displays **Card 1: Medication Intake**.
2. **Confirm Schedule:**
   > *"Confirm"*
   - Activates schedule and initializes dose events.
3. **Add New Drug & Trigger Safety Screening:**
   > *"Add ibuprofen 400mg as needed."*
   - Safety agent detects FDA label interaction between **Metformin + Ibuprofen** (renal function / lactic acidosis risk).
   - Generates **Card 2: Pharmacist Advisory** with official FDA label quotation and exact question to ask the pharmacist.
4. **Log Dose Confirmation:**
   > *"Taken"*
   - Updates dose event log and decrements inventory runway.
5. **Refill Check & Price Carousel:**
   > *"Refill Metformin"*
   - Returns **Card 4: Price Carousel** comparing Costco Pharmacy, Walgreens, and CVS Health.
6. **Select Pharmacy & Authorize Payment:**
   > *"Select Option 1"*
   > *"Approve & Pay"*
   - Dispatches Payment Protocol request (`pay_...`), records authorization, and replenishes supply.
7. **Caregiver Weekly Report:**
   > *"How did Dad do this week?"*
   - Computes adherence score (taken vs missed) and returns summary.
8. **Injected Failure Demo (Reliability):**
   - Run with `FAULT_INJECT=pricing_timeout` to show the partner timeout handled by circuit breaker and fallback to CMS NADAC reference estimates.
9. **Emergency Guardrail:**
   > *"My dad took too many pills and has chest pain!"*
   - Immediate emergency guidance with local emergency numbers and Poison Control hotline.

---

## 6. Agentverse Registration

Inspect agent addresses and copy-paste profile descriptions:
```powershell
.\run.ps1 register
# or
python scripts/register_agents.py
```

Deterministic Addresses:
- **Guardian Orchestrator:** `agent1q09642fqjyuhjrcpupdwcskl7n3890zw6y6py3n8ugcfjvw8cayr6zcd0lx`
- **Schedule Agent:** `agent1q2ae6hn2lqrsagylxq070znnja200nlmxdc64hemvw2k9afxsxq6jrmxd44`
- **Safety Agent:** `agent1q2p0afc3e88zdvcaeklzrqxhraa5uzefldwjlyxgdya0zd0n7qfqc8s99nr`
- **Pharmacy Agent:** `agent1q0xte8vak3zx99s5d9sm6qp0s9jkrf6a4kul7598uuwt03efax4fgn43sgn`
- **Caregiver Agent:** `agent1q2qkmp43f2qu82rt6t6v4ql4p2axkav8qk5dpdf82v7s4cptqh8mjx0zud9`

---

## 7. License

MIT License. Designed and built for the ASI:One Hackathon.
