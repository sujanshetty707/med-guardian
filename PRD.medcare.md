# PRD: Med-Guardian

**An ASI:One-native medication adherence, refill and caregiver-alert agent system**

| | |
|---|---|
| Version | 0.1 (Hackathon MVP) |
| Platform | Fetch.ai Agentverse + ASI:One (Agent Chat Protocol) |
| Build environment | Google Antigravity |
| Positioning | Adherence **support**, not medical advice |

---

## 1. Problem

- Roughly half of people on chronic medication don't take it as prescribed. Missed doses and refill gaps drive avoidable hospitalizations.
- Adult children caring for elderly parents (often remotely) have no lightweight way to know "did Mom take her 8am pills?" or "is her refill running out?"
- Multi-drug patients (polypharmacy) rarely have anyone cross-checking a newly added drug against the existing list.
- Pharmacy prices for the same drug vary widely, and nobody compares them on a routine refill.
- Today this means juggling a pill-reminder app, a pharmacy app, a drug-info website, and phone calls to family.

## 2. Vision

One conversation in ASI:One replaces all of that. The user (or their caregiver) says what they need in plain language; a team of agents tracks doses, flags interaction **questions to ask a pharmacist**, finds the cheapest refill, and alerts family when a dose is missed. No custom frontend and no extra app for the primary workflow.

## 3. Target Users

| Persona | Description | Core need |
|---|---|---|
| **Caregiver "Priya"** (primary buyer) | 35-55, remote adult child managing a parent's meds | Peace of mind, missed-dose alerts, refill automation |
| **Patient "Ramesh"** | 65+, 3-8 daily medications | Simple reminders, no new app to learn |
| **Self-managing adult** | Chronic condition (diabetes, hypertension, thyroid) | Never run out; lower cost |
| **Future B2B** | Pharmacies, insurers, home-care agencies | Adherence uplift, refill capture |

## 4. Goals and Non-Goals

### Goals
1. Complete the primary workflow (onboard, schedule, remind, detect miss, alert, refill) inside ASI:One.
2. Demonstrate real multi-agent orchestration with tool calls and failure recovery.
3. Show a credible monetization path via Payment Protocol.
4. Be safe by design: clear scope limits, no diagnosis, no dosage changes.

### Non-Goals (explicit)
- Not diagnosing, recommending, starting, stopping or changing any medication or dose.
- Not a substitute for a pharmacist or doctor.
- Not a prescription issuer. Refill orders only for medications the user already has a valid prescription for.
- No native mobile app or custom web frontend for the primary flow.

## 5. Hackathon Requirements Mapping

| Requirement | How Med-Guardian meets it |
|---|---|
| Agent registered on Agentverse | All 5 agents registered with profile pages and README |
| Implements ACP | Every agent uses the Agent Chat Protocol (`ChatMessage` / `ChatAcknowledgement`) |
| Discoverable and usable via ASI:One | Orchestrator has a strong description, keywords and handle; tested via ASI:One chat |
| Meaningful tool execution / orchestration | Orchestrator delegates to specialist agents, which call RxNorm, openFDA, pricing data, notifications, calendar |
| Primary workflow inside ASI:One | Setup, approvals, refill, and status all run in chat plus Interactive Cards |
| Public GitHub repo with run/test steps | See Architecture doc, section 12 |
| **Bonus:** multi-agent collaboration | 5 agents with distinct responsibilities |
| **Bonus:** Payment Protocol | Refill checkout and premium caregiver tier |
| **Bonus:** Interactive Cards | Med list form, interaction review, price carousel, refill approval |
| **Bonus:** reliability | Retries, fallbacks, circuit breakers, degraded-mode messaging |
| **Bonus:** real-time data | Live drug normalization, label data, price datasets |
| **Bonus:** continues post-hackathon | Persistent DB, pluggable adapters, B2B roadmap |

## 6. Key User Stories

**Onboarding**
- As a caregiver, I add my mother's medications by typing or pasting a list ("Metformin 500mg twice a day with meals, Amlodipine 5mg morning").
- As a user, I confirm the parsed schedule on a card before anything is saved.

**Daily adherence**
- As a patient, I get a reminder at dose time on my preferred channel and reply "taken" or "skip".
- As a caregiver, if a dose isn't confirmed within the grace window, I get an alert, and I can tap "Call her" or "Snooze".

**Safety**
- As a user adding a new drug, I see "possible interaction flagged. Ask your pharmacist about X + Y" with the source label cited.

**Refills and cost**
- As a user, I'm told 7 days before supply runs out, shown 3 price options, and approve a refill with one tap.

**Family**
- As a caregiver, I ask "how did Dad do this week?" and get an adherence summary.

## 7. Functional Requirements

### P0 (must ship for demo)
| ID | Requirement |
|---|---|
| F1 | Natural-language medication intake, parsed into structured schedule (drug, strength, frequency, timing, quantity on hand) |
| F2 | Drug name normalization to RxNorm (RxCUI) with fuzzy-match confirmation |
| F3 | Dose-reminder scheduling with timezone support |
| F4 | Dose confirmation ("taken", "skipped", "later") |
| F5 | Missed-dose detection with configurable grace window and escalation to caregiver |
| F6 | Interaction screening against the medication list, framed as questions for a pharmacist, with sources |
| F7 | Refill-runway calculation (days of supply left) and refill alert |
| F8 | Price comparison across pharmacy sources (adapter-based) |
| F9 | Refill order with explicit user approval (Interactive Card) |
| F10 | Mandatory safety disclaimer and scope guardrails on every medical-adjacent response |

### P1 (strong bonus)
| ID | Requirement |
|---|---|
| F11 | Payment Protocol for refill checkout and caregiver premium subscription |
| F12 | Weekly adherence report for caregiver |
| F13 | Multi-patient households (caregiver manages several people) |
| F14 | Consent management: the patient explicitly authorizes caregiver visibility |

### P2 (roadmap)
- Pharmacy partner API integration, insurer formulary checks, refill-gap analytics for B2B, voice calls via telephony, wearable/pill-box integration.

## 8. Safety, Privacy and Compliance

| Area | Policy |
|---|---|
| Medical scope | Adherence support only. Never suggest dose changes, substitutions or diagnoses. Interaction output is "discuss with your pharmacist or doctor." |
| Emergency | If the user mentions overdose, severe reaction, chest pain, etc., stop the workflow and show emergency guidance (local emergency number) immediately |
| Consent | Caregiver linking requires patient consent, recorded with timestamp |
| Data minimization | Store only what's needed: drug name, strength, schedule, adherence log. No diagnoses, no insurance IDs in MVP |
| Encryption | TLS in transit, encrypted at rest, secrets in environment variables |
| Retention and deletion | "Delete my data" command wipes all records |
| Logging | No PHI in application logs; use pseudonymous IDs |
| Regulatory note | A production release handling real health data would need HIPAA/DPDP (India) review. The hackathon build uses synthetic demo data |
| Payments | Never store card data; payments run through Payment Protocol or an external payment link |

## 9. Primary Demo Flow (inside ASI:One)

1. **User:** "I'm managing my dad's medicines. Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin."
2. **Card 1:** parsed med list and schedule, with Confirm / Edit.
3. **Safety agent** runs. **Card 2:** "No interaction notes found in label data" or "1 item to ask the pharmacist."
4. **User:** "Add ibuprofen 400mg as needed." The Safety agent flags a label-based question with a source link.
5. Simulated time passes. The 8am dose gets no confirmation. The Reminder agent re-pings, then the Alert agent notifies the caregiver. **Card 3:** Call / Snooze / Mark taken.
6. Metformin runway hits 7 days. Pharmacy agent returns **Card 4: price carousel** (3 options).
7. User taps one. **Card 5:** order summary with Payment Protocol request. User approves and the order is placed (simulated pharmacy).
8. **Failure demo:** the primary price source times out. The agent retries, falls back to the dataset, and tells the user the quote is an estimate.

## 10. Interactive Cards Plan

| Card | Purpose | Actions |
|---|---|---|
| Medication intake | Confirm parsed schedule | Confirm / Edit / Cancel |
| Interaction review | Show flagged items with sources | Acknowledge / Ask pharmacist (copyable question) |
| Dose check-in | Respond to a reminder | Taken / Skip / Later |
| Missed-dose alert (caregiver) | Escalation | Call / Snooze / Mark taken |
| Price carousel | Compare refill options | Select |
| Refill approval | Final confirmation and payment | Approve & Pay / Cancel |

> Verify the current Interactive Card schema in the ASI:One docs during build, and ship a plain-text fallback for every card.

## 11. Monetization

| Tier | Price (illustrative) | Includes |
|---|---|---|
| Free | $0 | 1 patient, 5 meds, reminders, basic interaction check |
| **Family** | $6-9/month | Up to 4 patients, caregiver alerts, weekly reports, price comparison |
| **Family+ (Payment Protocol)** | Per-refill service fee (~$1-2) or affiliate share | Automated refill ordering |
| **B2B** | Per-patient/month | Pharmacy refill capture, insurer adherence dashboards |

**Market logic:** Medication non-adherence is a multi-billion-dollar cost problem, and the caregiver segment is large and growing as populations age. Revenue is tied to a measurable outcome (refills kept on time).

## 12. Success Metrics

| Metric | MVP target (demo) | Production target |
|---|---|---|
| Medication parse accuracy | ≥ 90% on 20 test inputs | ≥ 95% |
| Reminder delivery success | ≥ 99% | ≥ 99.5% |
| Missed-dose to caregiver alert latency | < 60s after grace window | < 30s |
| Refill-on-time rate | n/a | +20% vs baseline |
| Tool-failure recovery | 100% of injected failures handled gracefully | same |
| Weekly active caregivers | n/a | retention ≥ 40% at week 4 |

## 13. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Interaction output mistaken for medical advice | Strict phrasing templates, always cite source, always route to pharmacist |
| LLM hallucinating drug data | LLM only parses and formats. Facts come from RxNorm/openFDA responses only |
| No free real-time pharmacy price API | Adapter pattern. Use public reference data plus a mock partner adapter, labeled as estimates |
| Proactive reminders can't be pushed into an ASI:One chat on demand | Reminders go over an external channel (Telegram/SMS/email); ASI:One handles setup, approvals, and status |
| Privacy concerns | Consent flow, minimal data, synthetic demo data |
| Agent downtime | Mailbox queueing, retries, health-check endpoint |

## 14. Milestones

| Phase | Deliverable |
|---|---|
| Day 1 | Orchestrator + ACP + Agentverse registration, intent parsing, med intake |
| Day 2 | Schedule/adherence agent, reminders, missed-dose escalation |
| Day 3 | Safety agent (RxNorm + openFDA), pricing agent, Interactive Cards |
| Day 4 | Payment Protocol, failure handling, tests |
| Day 5 | README, demo video, shared chat URL, Devpost write-up |

## 15. Deliverables Checklist (Devpost)

- [ ] ASI:One shared chat URL showing the full flow
- [ ] Agentverse profile URL for each of the 5 agents
- [ ] Public GitHub repo with README, `.env.example`, test script
- [ ] 2-3 minute demo video (include the failure-recovery moment)
- [ ] Project description: problem, target users, outcome
