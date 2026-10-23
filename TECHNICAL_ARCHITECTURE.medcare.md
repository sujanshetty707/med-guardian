# Technical Architecture: Med-Guardian

Companion to `PRD.md`. Target: **Fetch.ai uAgents on Agentverse, discoverable via ASI:One, built in Google Antigravity.**

> **Verify before building:** Agentverse, uAgents, ASI:One and Interactive Card APIs change quickly. Check the official docs (docs.agentverse.ai, uagents.fetch.ai, docs.asi1.ai) for current import paths and schemas. Items marked ⚠️ are the ones most likely to differ.

---

## 1. Architecture Overview

```
                    ┌─────────────────────────────┐
                    │          ASI:One            │
                    │  (chat + Interactive Cards) │
                    └──────────────┬──────────────┘
                                   │ Agent Chat Protocol (ACP)
                                   ▼
┌───────────────────────────────────────────────────────────────┐
│                     Agentverse (registry + mailbox)           │
│                                                               │
│   ┌─────────────────────────────────────────────────────┐     │
│   │  1. GUARDIAN ORCHESTRATOR  (ASI:One-facing)         │     │
│   │     intent parsing · planning · session state       │     │
│   └──┬──────────┬───────────┬────────────┬──────────────┘     │
│      │ uAgent msgs (typed Pydantic models, agent-to-agent)    │
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

**Hosting model:** Agents run as **mailbox agents** (code on your server or a cloud host, registered to Agentverse via mailbox) rather than purely Agentverse-hosted. Reason: the full stack needs a database, scheduler, HTTP clients and third-party SDKs, and Agentverse-hosted agents have a restricted runtime and package set. Mailbox agents still get an Agentverse profile, discoverability, and ASI:One routing. ⚠️ If you want a fully hosted agent, keep the orchestrator thin and move heavy logic behind HTTPS tool endpoints.

---

## 2. Agent Roster

| # | Agent | Role | Talks to ASI:One? | Key tools |
|---|---|---|---|---|
| 1 | **Guardian Orchestrator** | Entry point; intent classification, planning, delegation, card rendering | **Yes (ACP)** | ASI1 LLM, session store |
| 2 | **Schedule & Adherence** | Parse schedules, reminders, dose log, missed-dose detection, runway calc | Via orchestrator | DB, scheduler, notification gateway |
| 3 | **Safety (Interaction)** | RxNorm normalization, label-based interaction screening | Via orchestrator | RxNav/RxNorm, openFDA, DailyMed |
| 4 | **Pharmacy & Pricing** | Price comparison, refill order | Via orchestrator | Price adapters, Payment Protocol |
| 5 | **Caregiver Alert** | Escalation, consent, weekly report | Via orchestrator | Telegram/Twilio/SMTP |

All five: registered on Agentverse with README, ACP implemented, health endpoint. Only the Orchestrator *must* be user-facing, but implementing ACP on all five satisfies the requirement conservatively and lets each be tested independently.

---

## 3. Repository Layout

```
med-guardian/
├── README.md
├── PRD.md
├── TECHNICAL_ARCHITECTURE.md
├── .env.example
├── pyproject.toml / requirements.txt
├── docker-compose.yml
├── Makefile                      # make run, make test, make seed
├── agents/
│   ├── orchestrator/agent.py
│   ├── schedule/agent.py
│   ├── safety/agent.py
│   ├── pharmacy/agent.py
│   └── caregiver/agent.py
├── core/
│   ├── models.py                 # Pydantic inter-agent messages
│   ├── acp.py                    # ACP helpers (ack, reply, session)
│   ├── cards.py                  # Interactive Card builders + text fallbacks
│   ├── llm.py                    # ASI1 client, structured-output parsing
│   ├── db.py                     # SQLAlchemy models + session
│   ├── scheduler.py              # APScheduler / agent intervals
│   ├── resilience.py             # retry, timeout, circuit breaker, cache
│   ├── guardrails.py             # scope + emergency checks, disclaimers
│   └── config.py
├── tools/
│   ├── rxnorm.py
│   ├── openfda.py
│   ├── pricing/
│   │   ├── base.py               # PriceProvider interface
│   │   ├── nadac.py              # public CMS reference data
│   │   └── mock_partner.py       # simulated pharmacy partner
│   ├── notify/
│   │   ├── telegram.py
│   │   ├── twilio_sms.py
│   │   └── email.py
│   └── payments.py               # Payment Protocol wrapper
├── tests/
│   ├── test_parsing.py
│   ├── test_interactions.py
│   ├── test_missed_dose.py
│   ├── test_failures.py          # injected timeouts / 500s
│   └── e2e_chat_sim.py           # simulates ASI:One ACP messages
└── scripts/
    ├── register_agents.py
    └── seed_demo_data.py
```

---

## 4. Agent Chat Protocol (ACP) Implementation

Every agent includes the chat protocol, acknowledges every message, and replies with `ChatMessage`.

```python
# agents/orchestrator/agent.py  (⚠️ verify import paths against current uagents_core)
from datetime import datetime
from uuid import uuid4
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent,
    EndSessionContent, StartSessionContent, chat_protocol_spec,
)

agent = Agent(
    name="med-guardian",
    seed=SEED_PHRASE,          # from env, never committed
    port=8000,
    mailbox=True,              # connects to Agentverse mailbox
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    # 1. Acknowledge immediately (required by ACP)
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

    text = "".join(c.text for c in msg.content if isinstance(c, TextContent))
    reply = await orchestrate(ctx, sender, text)       # see section 5

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(), msg_id=uuid4(),
        content=[TextContent(type="text", text=reply)],
    ))

@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"ack from {sender}")

agent.include(chat_proto, publish_manifest=True)
```

**Registration checklist (per agent):**
1. Run locally. The console prints the inspector/mailbox link.
2. Open it, **Connect → Mailbox**, and the agent appears in Agentverse.
3. Fill in the profile: clear **description**, **keywords** (`medication`, `reminder`, `refill`, `caregiver`, `pharmacy`, `adherence`), and a README with example prompts.
4. Confirm `publish_manifest=True` so the chat protocol is visible to ASI:One.
5. Test from ASI:One with **Agents** mode enabled and search by handle or description.

ASI:One discovery is driven largely by the quality of the README and description, so write them like search-engine copy and include 3-5 sample prompts.

---

## 5. Orchestration Logic

### 5.1 Intent → Plan

The Orchestrator uses an ASI1 (OpenAI-compatible) LLM call with a strict JSON schema to classify intent. The LLM only **classifies and extracts**. Facts come from tools.

| Intent | Plan (ordered steps) |
|---|---|
| `ADD_MEDICATIONS` | parse → normalize (Safety) → interaction check (Safety) → confirm card → persist (Schedule) → schedule reminders |
| `LOG_DOSE` | resolve dose event → update log (Schedule) → ack |
| `CHECK_STATUS` / `WEEKLY_REPORT` | query adherence (Schedule) → summary card |
| `CHECK_INTERACTION` | normalize → interaction (Safety) → card |
| `REFILL` | runway check (Schedule) → price compare (Pharmacy) → carousel → approval → payment → order |
| `LINK_CAREGIVER` | consent flow (Caregiver) |
| `OUT_OF_SCOPE_MEDICAL` | guardrail response (no tool calls) |
| `EMERGENCY` | emergency guidance immediately |

### 5.2 Pseudocode

```python
async def orchestrate(ctx, sender, text):
    guard = guardrails.pre_check(text)           # emergency / dosing-advice detection
    if guard.block:
        return guard.response

    state = await sessions.load(sender)           # persisted conversation + pending actions
    intent = await llm.classify(text, state)      # structured output

    if state.pending_action and intent.is_confirmation:
        return await resume_pending(ctx, state, intent)

    plan = PLANS[intent.name](intent.entities)
    results = {}
    for step in plan:
        results[step.name] = await run_step(ctx, step, results)   # may delegate to agents
        if results[step.name].needs_user_input:
            state.pending_action = step
            await sessions.save(sender, state)
            return cards.render(step, results)                    # interactive card + text fallback

    return guardrails.post_format(cards.render_final(plan, results))
```

### 5.3 Inter-Agent Messaging

Typed Pydantic models in `core/models.py`, sent via `ctx.send` or `ctx.send_and_receive`. ⚠️ Confirm the current request/response pattern in your uAgents version.

```python
class NormalizeRequest(Model):  session_id: str; raw_names: list[str]
class NormalizeResponse(Model): session_id: str; items: list[NormalizedDrug]; unresolved: list[str]

class InteractionRequest(Model):  session_id: str; rxcuis: list[str]
class InteractionResponse(Model): session_id: str; findings: list[Finding]; source_status: str  # ok | degraded

class PriceRequest(Model):  session_id: str; rxcui: str; strength: str; qty: int; zip_code: str
class PriceResponse(Model): session_id: str; quotes: list[Quote]; is_estimate: bool

class MissedDoseEvent(Model): patient_id: str; med_name: str; due_at: datetime; attempts: int
```

Every message carries `session_id` for tracing.

---

## 6. Data Sources and Tools

### 6.1 Drug normalization: RxNorm (NLM)
- Endpoint family: `https://rxnav.nlm.nih.gov/REST/` (e.g., `approximateTerm`, `rxcui`, `properties`).
- Handles brand/generic names and misspellings. Returns RxCUI used as the canonical drug ID.

### 6.2 Interaction screening, with an important caveat
> ⚠️ NLM **discontinued the RxNav Drug Interaction API** (early 2024). Do not build on it.

Recommended approach for the MVP:
- **openFDA drug label API** (`https://api.fda.gov/drug/label.json`): query each drug's label and read the `drug_interactions` section.
- **Cross-reference:** for each pair (A, B), check whether A's label text mentions B's generic name or drug class, and vice versa.
- **LLM role (restricted):** summarize the matched label snippet in plain language and extract the cited sentence. It must not invent interactions and may only restate what the retrieved text says.
- **Output template (fixed):** *"The FDA label for {A} mentions {B/class}: "{short excerpt}". Please ask your pharmacist or doctor whether this matters for you."* Always include the source.
- **Upgrade path:** licensed databases (e.g., DrugBank, First Databank, Medi-Span) for production.

Limitations to state in the README: label text is not a complete interaction database, and absence of a flag **does not** mean no interaction.

### 6.3 Pricing
There is no free, public, real-time retail pharmacy price API. Use an adapter pattern:

```python
class PriceProvider(Protocol):
    name: str
    async def quote(self, rxcui: str, strength: str, qty: int, zip_code: str) -> list[Quote]: ...
```

| Provider | Use |
|---|---|
| `nadac.py` | CMS NADAC public dataset (average acquisition cost), used as a baseline price reference |
| `mock_partner.py` | Simulated pharmacies (e.g., 3 fictional chains) with realistic price spread and latency |
| *(future)* real partner API | Pharmacy/aggregator partnership |

Always label quotes **"estimate"** when not from a live partner API.

### 6.4 Notifications (reminders and alerts)
ASI:One chats are user-initiated, so scheduled reminders cannot be assumed to push into an ASI:One session. Use an external channel:
- **Telegram Bot** (free, fastest to demo; supports inline buttons for Taken/Skip)
- Twilio SMS or WhatsApp (production)
- Email fallback

Reply handling: Telegram webhook → Schedule agent → dose log updated. The ASI:One chat reflects the state on the next message and card refresh.

### 6.5 Calendar (optional)
Google Calendar API to mirror dose times. Skip for MVP.

---

## 7. Data Model

SQLite for dev, Postgres (Supabase/Neon) for deployment. Use SQLAlchemy.

```
users(id, asi_sender_addr, role[patient|caregiver], tz, channel, channel_addr, created_at)
patients(id, display_name, owner_user_id, tz)
caregiver_links(id, patient_id, caregiver_user_id, consent_at, revoked_at, alert_prefs)
medications(id, patient_id, rxcui, display_name, strength, form, instructions,
            qty_on_hand, qty_per_dose, last_refill_at, active)
schedules(id, medication_id, times[], days[], with_food, start_date, end_date)
dose_events(id, medication_id, due_at, status[pending|taken|skipped|missed],
            confirmed_at, attempts, source[telegram|sms|asi_one])
interaction_checks(id, patient_id, pair_a_rxcui, pair_b_rxcui, finding, source_url,
                   checked_at)
refill_orders(id, medication_id, provider, quote_cents, status, payment_ref, created_at)
sessions(sender_addr, state_json, pending_action_json, updated_at)
audit_log(id, actor, action, entity, ts)          # no PHI in message bodies
```

Pending-action state in `sessions` is what lets a card tap in ASI:One resume a half-finished workflow.

---

## 8. Scheduling and the Missed-Dose State Machine

```
 PENDING ──(due_at)──▶ REMINDED ──(taken)──▶ TAKEN
                          │
                          ├──(skip)──▶ SKIPPED
                          │
                    (no reply after grace T1, e.g. 20 min)
                          ▼
                     RE-REMINDED ──(taken)──▶ TAKEN
                          │
                    (no reply after T2, e.g. 40 min total)
                          ▼
                       MISSED ──▶ emit MissedDoseEvent ──▶ Caregiver Alert agent
```

- **Scheduler:** APScheduler inside the Schedule agent (or `@agent.on_interval(60)` polling a due-doses query). Poll every minute, since it is idempotent and crash-safe.
- **Idempotency:** unique key `(medication_id, due_at)` prevents duplicate reminders after restarts.
- **Runway:** `days_left = qty_on_hand / (qty_per_dose × doses_per_day)`. Refill flow triggers at ≤ 7 days (configurable).
- **Timezones:** store UTC, render in patient tz.

---

## 9. Interactive Cards

Implement `core/cards.py` with one builder per card and a **plain-text fallback** for each (some surfaces or older flows may not render cards).

```python
def price_carousel(quotes: list[Quote]) -> OutboundMessage:
    """Returns card payload + text fallback."""
```

⚠️ The Interactive Card schema and how it is attached to an ACP `ChatMessage` are defined in the ASI:One docs. Read them first, then adapt `cards.py`. Keep all card logic in this one module so any schema change is a one-file fix.

Card-tap events return to the Orchestrator as a message containing the action id (e.g., `refill.approve:<order_id>`), which resumes the `pending_action`.

---

## 10. Payment Protocol

Use the Agentverse/uAgents payment protocol for the refill checkout and the optional premium tier. ⚠️ Verify the module path and message names.

Flow:
1. Pharmacy agent → user: `RequestPayment` (amount, currency, description, recipient)
2. User approves in ASI:One → `CommitPayment` (with transaction reference)
3. Pharmacy agent verifies → places the order → `CompletePayment`
4. On decline or timeout → `RejectPayment` / `CancelPayment`, order marked `cancelled`, no side effects.

For the hackathon, run in the test/sandbox payment mode and be transparent that the pharmacy fulfilment is simulated. The monetization story is: **service fee per refill + subscription**, with a path to pharmacy referral revenue.

---

## 11. Reliability and Error Handling

Centralised in `core/resilience.py`.

| Failure | Handling |
|---|---|
| RxNorm timeout / 5xx | 3 retries with exponential backoff + jitter → local cache of common drugs → ask user to confirm spelling |
| openFDA unavailable / rate-limited | Retry → cached label snippets → respond `source_status=degraded`: *"I couldn't check interactions right now. Please ask your pharmacist."* Never silently report "no interactions" |
| Price provider fails | Circuit breaker → fall back to NADAC baseline → mark quotes as **estimates** |
| Notification send fails | Retry → alternate channel (Telegram → SMS → email) → log to audit |
| Sub-agent doesn't respond | Per-call timeout (e.g., 10s) → partial result + clear message → no half-written state |
| Duplicate/replayed ACP messages | Dedupe on `msg_id` |
| LLM returns invalid JSON | Re-prompt once → regex/heuristic fallback → ask the user to rephrase |
| Process crash | Stateless agents + DB state + idempotent scheduler |

**Demo tip:** add a `FAULT_INJECT=pricing_timeout` env flag so you can trigger a failure on camera and show the recovery. This directly targets the reliability bonus.

---

## 12. Guardrails (`core/guardrails.py`)

**Pre-check (before any tool call):**
- Emergency keywords (overdose, can't breathe, chest pain, suicidal, severe allergic reaction): return emergency guidance and stop.
- Dosing advice requests ("how much should I take", "can I stop", "double my dose"): decline politely and redirect to the pharmacist or doctor.

**Post-format:**
- Append a short non-diagnostic disclaimer to any interaction or medication-info reply.
- Strip any LLM statement not traceable to a tool result in interaction replies.

---

## 13. Configuration (`.env.example`)

```
# Agent identity (generate unique seeds; never commit real ones)
ORCHESTRATOR_SEED=
SCHEDULE_SEED=
SAFETY_SEED=
PHARMACY_SEED=
CAREGIVER_SEED=

AGENTVERSE_API_KEY=
ASI1_API_KEY=

DATABASE_URL=sqlite:///./medguardian.db
TELEGRAM_BOT_TOKEN=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM=

PRICE_PROVIDERS=nadac,mock_partner
FAULT_INJECT=
REMINDER_GRACE_MINUTES=20
MISSED_AFTER_MINUTES=40
REFILL_THRESHOLD_DAYS=7
LOG_LEVEL=INFO
```

---

## 14. Building in Google Antigravity

- Open the repo in Antigravity and keep `PRD.md` and this file in the root. The agent-assisted workflow uses them as context.
- Suggested task order for Antigravity's agents: (1) `core/models.py` + `core/db.py`, (2) orchestrator ACP skeleton, (3) each specialist agent with tests, (4) cards, (5) payments, (6) e2e simulator.
- Have the IDE agent generate unit tests alongside each tool wrapper, and use the browser/terminal tools to run `make test`.
- Antigravity is only the dev environment. The runtime is plain Python (uAgents), so nothing here is Antigravity-specific and it deploys anywhere.

---

## 15. Deployment

| Option | Notes |
|---|---|
| **Local + mailbox (dev/demo)** | Run `make run`; connect each agent to Agentverse via mailbox. Fastest. Keep the machine online during judging |
| **Cloud (recommended for submission)** | Docker on Render / Railway / Fly.io / Cloud Run with a persistent DB. Agents stay reachable 24/7 via mailbox |
| **Agentverse-hosted** | Possible for thin agents; limited packages and persistence. Use for the orchestrator only if you can keep dependencies minimal ⚠️ |

`docker-compose.yml` runs the 5 agents + Postgres. Each agent needs a stable seed so its address stays constant across restarts, and **losing the seed means re-registering**.

---

## 16. Testing Strategy

| Layer | Tests |
|---|---|
| Unit | Schedule parsing (20+ phrasings), runway math, state machine transitions, guardrail triggers |
| Tool | RxNorm/openFDA wrappers against recorded fixtures (VCR-style) |
| Failure | Injected timeouts/500s per dependency, assert graceful degradation |
| Integration | Agent-to-agent message round-trips using local agents |
| E2E | `e2e_chat_sim.py` sends scripted ACP `ChatMessage`s and asserts replies/cards |
| Manual | Real ASI:One session with Agents mode on, using the demo script from the PRD |

README must include: install steps, `.env` setup, `make seed`, `make run`, `make test`, and the exact ASI:One prompts to try.

---

## 17. Submission Pack

1. Record the full demo in ASI:One and copy the **Shared Chat URL**.
2. Collect the 5 **Agentverse profile URLs**.
3. Push a public GitHub repo (no secrets, `.env.example` only).
4. 2-3 minute video: intake, interaction flag, missed dose alert, refill with payment, **one injected failure and recovery**.
5. Devpost text: problem, target users (caregivers, patients), outcome (fewer missed doses, no refill gaps, lower cost).

---

## 18. Future Roadmap

- Real pharmacy/aggregator APIs and insurer formulary checks
- Licensed interaction database
- Voice-call escalation for elderly users without smartphones
- Smart pill-box / wearable integration
- B2B dashboard for pharmacies and home-care agencies
- Regulatory path (HIPAA / India DPDP) and clinical review of interaction messaging
