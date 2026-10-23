# Med-Guardian 🛡️💊
**ASI:One-Native Medication Adherence, Refill & Caregiver Alert System**

Med-Guardian is an autonomous healthcare adherence assistant built natively on the **Fetch.ai uAgents** framework and discovered via **ASI:One**. It coordinates a multi-agent team to parse natural language medication schedules, flag drug interactions from FDA label data, compare pharmacy prices, and alert remote family caregivers when doses are missed.

---

## 🎯 What Med-Guardian Does

- 📋 **Natural Language Intake:** Paste or type your regimen in plain English; Med-Guardian normalizes drug names to **RxNorm (RxCUI)** and builds an automated schedule.
- 🛡️ **FDA Label Safety Screening:** Screens multi-drug combinations against official **openFDA** drug label interaction data, framing actionable questions for your pharmacist.
- ⏰ **Adherence Tracking & Reminders:** Tracks dose events, confirmations, and calculates days of supply left (refill runway).
- 🚨 **Caregiver Escalation:** Automatically alerts remote adult children/family caregivers via Telegram or SMS when a scheduled dose is missed past the grace window.
- 💊 **Multi-Pharmacy Price Comparison:** Compares refill prices across partner pharmacies (Costco, Walgreens, CVS) and CMS NADAC reference benchmarks.
- 🛒 **Payment Protocol Refill Orders:** Authorizes refill checkouts seamlessly using the Fetch.ai / ASI:One Payment Protocol.
- 📊 **Weekly Adherence Reports:** Generates summary reports and adherence scores for peace of mind.

---

## 💬 Try These Prompts in ASI:One

### 1. Medication Intake & Schedule Setup
> *"I'm managing my dad's medicines: Metformin 500mg twice daily, Amlodipine 5mg morning, Atorvastatin 20mg night. He has 10 days left of Metformin."*

### 2. Safety & Drug Interaction Screening
> *"Add ibuprofen 400mg as needed."*  
*(Flags potential NSAID interaction with Metformin from FDA label data and provides a question to ask your pharmacist).*

### 3. Log Dose Confirmation
> *"Taken"* or *"Skip"*

### 4. Pharmacy Price Comparison & Refill
> *"Refill Metformin"*  
*(Returns a 3-option price carousel comparing Costco Mail Order, Walgreens, and CVS).*

### 5. Authorize Refill Checkout
> *"Select Option 1"*  
*(Followed by)*: *"Approve & Pay"*

### 6. Family Adherence Summary
> *"How did Dad do this week?"*

---

## ⚠️ Safety & Scope Notice

*Med-Guardian is an adherence organization and scheduling assistant, not a doctor or pharmacist. It does not provide medical diagnosis, prescribe drugs, or adjust dosages. In acute emergencies, Med-Guardian immediately directs users to 911 and Poison Control (1-800-222-1222).*

---

## 🔗 Technical Details & Open Source

- **Protocol:** Agent Chat Protocol (ACP)
- **Framework:** Fetch.ai uAgents + Agentverse
- **Data Sources:** NLM RxNorm, openFDA Drug Labels, CMS NADAC Reference Pricing
- **GitHub Repository:** [https://github.com/sujanshetty707/med-guardian](https://github.com/sujanshetty707/med-guardian)
- **Built for:** ASI:One Hackathon
