# MediKiosk (PS 26047) vs New PS 26133 — Gap & Overlap Analysis

## TL;DR

Your MediKiosk is **extremely well-aligned** with PS 26133. You've done *more* than what's asked in most areas (which is a **strength**, not a weakness — it shows depth). However, there are **~5–6 specific features** the new PS explicitly asks for that you **don't currently have**. These are all buildable.

---

## ✅ What You Already Cover (Strong Overlap)

| PS 26133 Requirement | Your MediKiosk Coverage | Status |
|---|---|:---:|
| **Assisted teleconsultation** | Your voice intake + structured SOAP summaries create the *foundation* for teleconsultation (doctor gets a pre-built summary) | ⚠️ Partial |
| **Digital triage** | Red-flag detection, Bayesian life-threat screening, Arishta Lakshana emergency screening, priority queue alerts | ✅ Excellent |
| **Longitudinal patient records** | Supabase pgvector with patient-scoped lifetime records (20–50+ docs), chronological timeline view, OCR of past records | ✅ Excellent |
| **Diagnostic coordination** | OCR pipeline extracts lab values, flags abnormal results, structures prescriptions & discharge summaries | ✅ Strong |
| **Frontline health worker support** | Kiosk designed for minimal staff assistance, icon-driven UI, audio-guided consent | ✅ Strong |
| **Low-connectivity environments** | Dual-tier storage (SQLite WAL + Supabase), offline-resilient local persistence, survives power loss | ✅ Excellent |
| **Multilingual interaction** | 11 Indic languages via Sarvam AI (Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Malayalam, Punjabi, Odia, English) | ✅ Excellent |
| **Interoperable health records (approved standards)** | ABDM/ABHA integration, FHIR-compliant bundles, DPDP Act 2023 compliance | ✅ Strong |
| **Reduced travel and waiting time** | Pre-consultation intake means doctor spends minutes on examination, not history-taking | ✅ Strong |
| **Earlier consultation** | Progressive SSE streaming, ~1.5s perceived response, adaptive questioning | ✅ Strong |
| **Improved follow-up for chronic conditions** | Patient RAG scoped by `patient_id`, past medical history cross-referencing (e.g., T2DM → Prameha) | ✅ Strong |

---

## ❌ What PS 26133 Asks For That You DON'T Have

These are the **gaps you need to fill** to make your submission convincing for the new PS:

### 1. 🗓️ Appointment & Queue Management System
> *"appointment and queue management"*

**What's missing:** You have no appointment booking, scheduling, or OPD queue management feature. Your kiosk does intake but doesn't manage the patient's position in a queue, estimated wait times, or let them book/reschedule appointments.

**Effort to add:** Medium — a queue dashboard showing token numbers, estimated wait times, and doctor availability. Could be a simple real-time queue board.

---

### 2. 🔄 Referral Tracking
> *"referral tracking... improved referral completion"*

**What's missing:** When a patient is referred from a sub-centre → PHC → rural hospital → district hospital, there's no tracking of whether the referral was completed, the referral chain, or alerts for dropped referrals.

**Effort to add:** Medium — add a referral status field to patient records, track referral origin/destination, and show completion status on facility dashboards.

---

### 3. 💊 Medicine Availability / Inventory Visibility
> *"medicine availability... improved medicine/diagnostic availability visibility"*

**What's missing:** Your system doesn't track or display drug stock/availability at the facility. Patients and health workers can't see if prescribed medicines are available at the pharmacy or nearby facilities.

**Effort to add:** Medium — integrate with facility pharmacy inventory (even a simple stock table) and show availability alongside prescriptions.

---

### 4. 📊 Facility Dashboards (Admin/Quality Monitoring)
> *"facility dashboards... enhanced quality monitoring"*

**What's missing:** You have a doctor-facing SOAP note output, but no **facility-level dashboard** showing aggregate metrics: patients seen per day, average wait times, referral completion rates, medicine stockouts, diagnostic equipment utilization, etc.

**Effort to add:** Medium — build a simple admin dashboard with charts aggregating data you already collect.

---

### 5. 🚨 Emergency Escalation Workflow
> *"emergency escalation"*

**What's missing:** You detect red flags and mark triage priority, but there's no **explicit escalation workflow** — e.g., auto-notifying the nearest emergency ward, sending SMS/alerts to duty doctors, or triggering an ambulance dispatch protocol.

**Effort to add:** Low-Medium — wire your existing red-flag detection to send push notifications / SMS to designated emergency contacts.

---

### 6. 👩‍⚕️ High-Risk Patient Follow-Up System
> *"high-risk patient follow-up... better follow-up for maternal, child and chronic conditions"*

**What's missing:** While you have patient RAG and chronic condition cross-referencing, there's no **proactive follow-up system** — automated reminders for ANC visits, immunization schedules, chronic disease check-ups, or flagging patients who missed follow-ups.

**Effort to add:** Medium — add a follow-up scheduler with SMS/notification reminders and a dashboard showing overdue follow-ups.

---

## ⚠️ Things You've Done That PS 26133 Doesn't Explicitly Ask For

These are **extras** — they're NOT a problem. They demonstrate depth and innovation. Just be aware of how to position them:

| Your Feature | PS 26133 Relevance | How to Position |
|---|---|---|
| **AYUSH/Ayurveda mode** (Prakriti, Dashavidha, NAMASTE codes) | Not mentioned at all — PS 26133 is from Govt of Maharashtra, not Ministry of Ayush | Frame as "extensible to AYUSH systems" or "dual-paradigm support for integrated medicine facilities" |
| **SOCRATES framework** deep clinical intake | PS asks for "digital triage" — your intake goes far beyond basic triage | Position as "AI-powered clinical decision support that goes beyond simple triage" |
| **Document OCR & digitization** | PS mentions "longitudinal patient records" and "diagnostic coordination" — OCR supports this | This fits well, keep it |
| **Conversational RAG with clinical guidelines** | Not explicitly asked but supports "quality" and "diagnostic coordination" | Frame as "evidence-based clinical decision support" |
| **Web Audio DSP / spectral subtraction** | Not mentioned but supports "low-connectivity" / rural environments | Frame as "designed for noisy rural health facility environments" |

---

## 🎯 Recommended Pivot Strategy

### Reframing (Low Effort, High Impact)
1. **Rename/rebrand** from "Patient Case-Taking Software" to **"Integrated Rural Healthcare Access & Quality Platform"**
2. Update all docs to reference **PS 26133** instead of 26047
3. Emphasize the **rural health worker support** angle — your multilingual, low-literacy, offline-capable design is *exactly* what rural healthcare needs
4. Frame the clinical intake as the **core differentiator** within a broader access platform

### Feature Additions (Prioritized)

| Priority | Feature | Why | Est. Effort |
|:---:|---|---|:---:|
| 🔴 P0 | **Queue/Appointment Management** | Explicitly called out in PS, highly visible feature | 2–3 days |
| 🔴 P0 | **Facility Dashboard** | Explicitly called out, judges love dashboards with charts | 2–3 days |
| 🟡 P1 | **Referral Tracking** | Core to the rural health chain narrative | 1–2 days |
| 🟡 P1 | **Emergency Escalation** (SMS/notification) | You already detect emergencies, just need the notification layer | 1 day |
| 🟢 P2 | **Medicine Availability** | Nice to have, can be a simple lookup table | 1 day |
| 🟢 P2 | **Follow-Up Reminders** | Strengthens the "continuity of care" narrative | 1–2 days |

---

## 📝 Summary Verdict

> **Can it be done?** Absolutely yes. Your MediKiosk is ~70% aligned with PS 26133 already. The core technology (multilingual voice, clinical intake, document digitization, offline resilience, FHIR/ABDM) is directly applicable.

> **What needs work?** You need to add **5–6 healthcare system features** (queues, referrals, dashboards, medicine stock, follow-ups, emergency escalation) that wrap *around* your existing clinical intake core. These are mostly CRUD/dashboard features, not deep AI work.

> **The AYUSH angle:** PS 26133 is from **Government of Maharashtra**, not Ministry of Ayush. The Ayurveda features aren't a liability (Maharashtra has Ayurveda hospitals too), but they shouldn't be the *lead pitch*. Lead with rural healthcare access, and mention AYUSH as a bonus.
