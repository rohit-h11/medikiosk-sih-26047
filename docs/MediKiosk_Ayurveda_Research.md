# MediKiosk — Research Reference: Dashavidha Pariksha, Vikriti/SOCRATES Prompting

*Compiled for Module A (Ayurveda) and Module B (Allopathy/SOCRATES) task sheet. Scope limited to what's relevant to your task: Steps A1–A5 and B1–B3.*

---

## 1. Dashavidha Pariksha — Static Questionnaires (Step A1/A2)

### 1.1 Prakriti — a validated scale exists, use it

This is the one parameter where an **official, validated, government scale already exists** — don't build your own questions for this.

- **Source**: CCRAS (Central Council for Research in Ayurvedic Sciences), Ministry of AYUSH — the **Prakriti Assessment Scale (PAS)**.
- **Structure**: 91 predictors grouped into 30 domains across **four trait categories**: physical, physiological, psychological, and behavioral. Of the 91 predictors, roughly 31 map to Vata (Vatika), 29 to Pitta (Paittika), and 32 to Kapha (Kaphaja) traits — each predictor typically carries one mark.
- **Validation**: Face, content, construct, and criterion validity were tested; reliability was checked via intra-rater/inter-rater agreement (Kappa statistic) across a multi-center double-blind study (10 centers, ~500 participants nationally).
- **Answer format**: Mostly multiple-choice, some Likert-scale items.
- **Digital version**: CCRAS built the **"Ayur Prakriti" web portal** to administer this scale digitally (in beta as of its published review). Portal reference: `ccras.res.in/ccras_pas/`. A published "Manual of Standard Operative Procedures for Prakriti Assessment" documents the SOP (copyright registration L-76725/2018).
- **Scoring output**: dosha percentages (Vata/Pitta/Kapha), stored once against the patient profile.
- **What to actually digitize**: Get the CCRAS PAS question bank/manual (search "CCRAS Prakriti Assessment Scale manual PDF" or the AYUR Prakriti portal) rather than inventing questions — judges familiar with AYUSH standards will recognize whether you used the real scale.
- Note: a 2025 review found **64 different Prakriti assessment tools** have been proposed in the literature since 1987, but CCRAS-PAS is the one with official Ministry of AYUSH backing and is the appropriate reference standard for an AIIA-facing submission.

### 1.2 Satmya, Sattva, Vyayama Shakti — no equivalent standalone official scale exists

This is an important finding for your submission: **unlike Prakriti, there is no CCRAS-published, independently validated multiple-choice scale specifically for Satmya, Sattva, or Vyayama Shakti** in isolation. What exists instead:

- **Classical descriptive criteria** (Charaka Samhita, Vimana Sthana Ch. 8) that define each parameter qualitatively, which several researchers have since converted into their own informal Likert-style research questionnaires (not government-standardized).
- A few individual research papers (e.g., published in IJLPR, JAIMS) have built **ad hoc scoring questionnaires** for Sattva assessment for their own studies, but none carry CCRAS/AYUSH endorsement the way Prakriti's PAS does.

**Recommendation for your submission**: Digitize the **classical criteria** below into a structured MCQ form, but explicitly label it in your documentation as *"digitized from classical Charaka Samhita criteria — no single AYUSH-validated scale currently exists for this parameter, unlike Prakriti."* This is exactly the kind of honest scoping distinction the task sheet says will read as clinical rigor rather than corner-cutting.

#### Satmya Pariksha (adaptability/suitability)
Classical sub-categories to build questions around:
- **Rasa Satmya** — habituation/tolerance to tastes (sweet, sour, salty, pungent, bitter, astringent)
- **Desha Satmya** — suitability to geographic/climatic region (hot/cold, dry/humid)
- **Ritu Satmya** — adaptability across seasons
- **Oka Satmya** — habituation to regularly consumed diet/habits even if not classically "wholesome"
- **Scoring**: classify as **Pravara** (high adaptability — tolerates wide variety without disturbance), **Madhyama** (moderate — some sensitivity/adjustment needed), **Avara** (poor — narrow tolerance, easily disturbed by dietary/climate change).

#### Sattva Pariksha (mental/psychic strength)
This is the most classically well-documented of the three, since Charaka gives explicit behavioral descriptors:

- **Pravara Sattva** (strong-minded): tolerates pain/disease without much distress, doesn't exaggerate symptoms, calm under stress, good memory, high enthusiasm, patient, doesn't need reassurance/consolation from others. Even physically weak, these individuals show high pain tolerance because of "Sattva Sara" qualities.
- **Madhyama Sattva** (moderate): can tolerate pain/distress but draws strength from seeing others cope; needs some reassurance and encouragement from others to hold steady.
- **Avara Sattva** (weak-minded): easily overwhelmed by pain, grief, fear, or disturbing sensory input (e.g., blood, frightening stories); not consoled even by repeated reassurance; prone to fainting, giddiness, panic, or dissociation-like reactions under stress.

Practical question domains for a form: response to physical pain, response to grief/loss, response to fear/frightening situations, response to anger-provoking situations, need for reassurance from others, memory/decisiveness under stress.

#### Vyayama Shakti (exercise/exertion capacity)
Charaka pairs this with Ahara Shakti (digestive capacity) as functional-capacity indicators. No dedicated classical scoring scale beyond descriptive tiers:
- **Pravara**: high tolerance for heavy physical work/exercise, minimal fatigue/breathlessness.
- **Madhyama**: moderate tolerance, noticeable but manageable fatigue with exertion.
- **Avara**: low stamina, breathlessness/fatigue with mild exertion (e.g., stairs, short walks).

Practical question domains: daily activity level, breathlessness onset threshold (rest / mild exertion / moderate / heavy), recovery time after exertion, frequency of fatigue-related activity limitation.

### 1.3 Vaya
No questionnaire needed — pull directly from patient registration data (age in years; classical texts group into Bala/childhood, Madhya/middle, Vriddha/old age bands if you want an Ayurvedic life-stage label alongside the raw number).

### 1.4 Out of scope — confirmed correct to defer
**Sara** (tissue quality/excellence), **Samhanana** (structural compactness/build), and **Pramana** (anthropometric measurement) all require physical inspection/palpation/measurement by a physician and cannot be reliably self-reported through a kiosk conversation or form. Explicitly stating this deferral in your submission is accurate to classical methodology, not a shortcut — even classical texts treat these as physician-observed parameters.

---

## 2. Classical Symptom-to-Dosha Mapping (for Vikriti Prompt Grounding)

This maps to Charaka Samhita/Ashtanga Hridaya's classical lists of aggravation (Vriddhi) symptoms per dosha. Your Vikriti prompt's clinical-reference RAG chunks will likely draw on tables like this — useful for you to understand the shape of what you're prompting against, even though the RAG teammate builds the actual retrieval table.

### Vata Vriddhi Lakshana (Vata aggravation)
Pain and dryness-pattern symptoms: pricking pain (Toda), splitting/cutting pain (Bheda), stiffness (Stambha), tremors (Kampa), dryness (Rukshata), bloating/gas (Anaha), constipation (Vibandha), insomnia (Nidranasha), plus classically also: roughness of skin, joint cracking, and irregular bowel/appetite patterns.

### Pitta Vriddhi Lakshana (Pitta aggravation)
Heat/inflammation-pattern symptoms: burning sensation (Daha), suppuration/ulceration (Paka), redness (Raga), excessive sweating (Sweda), sharp/excessive hunger (Tikshnagni), sour eructation/acid reflux (Amlodgara), plus classically: fainting/giddiness from heat, yellowish discoloration of skin/eyes/stools, and increased thirst.

### Kapha Vriddhi Lakshana (Kapha aggravation)
Heaviness/congestion-pattern symptoms: heaviness (Gaurava), drowsiness/lethargy (Tandra), mucus/cough/breathlessness (Kasa/Shwasa), sluggish digestion (Agnimandya), weight gain (Sthaulya), edema/swelling (Shotha), plus classically: excessive salivation, pallor, and coldness of extremities.

### Baseline (Prakriti) vs. active imbalance (Vikriti) — the key distinguishing logic
This is the clinically subtle part your system prompt needs to encode (and the task sheet's template already gestures at this with the Pitta heat-tolerance example). The general classical principle:

- A symptom that matches a person's **natural constitutional tendency** (Prakriti) at a *stable, longstanding, non-progressive* level is **baseline**, not imbalance — e.g., a Pitta-dominant person having naturally warmer body temperature and stronger appetite than average; a Vata-dominant person naturally having lighter/interrupted sleep and quicker fatigue; a Kapha-dominant person naturally having a heavier build and slower digestion.
- It becomes **Vikriti (active imbalance)** when the symptom:
  1. Represents a **new deviation from that person's own usual baseline** (not just "unusual compared to an average person"), OR
  2. Has **increased in intensity or frequency** beyond what's typical even for their own constitution, OR
  3. Is **accompanied by other dosha-consistent aggravation symptoms** appearing together (clustering), OR
  4. Has an **identifiable trigger and time-course** (recent onset, correlates with a dietary/seasonal/lifestyle change) rather than being lifelong.
- Practically for prompt-writing: the LLM should always compare a reported symptom against the patient's *stored Prakriti result* before treating it as a Vikriti signal, and should explicitly ask a differentiating follow-up when a symptom is ambiguous (e.g., "Has this level of heat-sensitivity always been normal for you, or is it new/worse recently?").

---

## 3. Top AYUSH OPD Conditions — NAMASTE & ICD-11 TM2 (Corrected)

**Important correction to flag in your submission**: the code format `NAM-AYU-xxxx` / `TM2-XXnn.n` circulated in early planning notes appears to be **illustrative placeholder syntax, not the real coding scheme**. The actual NAMASTE codes follow a different alphanumeric pattern (short alphabetic category prefix + numeric suffix, e.g. `AAE-16`), and TM2 codes follow WHO ICD-11's own foundation-ID/coding conventions on the ICD-11 Browser — not a `TM2-XXnn.n` style. Below is what's actually documented in published NAMASTE portal data analyses. Get exact/current codes from the live NAMASTE portal (namaste.ayush.gov.in) or ICD-11 Browser TM2 chapter rather than from any pre-built table, since codes are still being finalized/expanded (portal mapped 1,941 national codes to ICD-11 TM2 as of Feb 2025, and TM2 itself covers 529 disorder categories + 196 pattern codes).

### Confirmed real NAMASTE codes (from published portal data analysis)

| Ayurvedic Name | English/Clinical Correlate | Real NAMASTE Code (documented) |
|---|---|---|
| Sandhigatavata | Osteoarthritis | **AAE-16** (most commonly recorded code nationally) |
| Vatavyadhi (general) | Vata-origin disorders | **AA** (top-level category) |
| Amavata | Rheumatoid arthritis | **EC-6** |
| Amlapitta | GERD / hyperacidity | **EB-4** |
| Grahani Dosha | IBS / malabsorption | **EB-7** (Grahanidosha) |
| Kasa | Cough | **EA-3** |
| Shwasa | Asthma/dyspnea (Tamaka Shwasa is a sub-type) | **EA-4** |
| Gridhrasi / Grudhrasi | Sciatica | **AAB-37 / AAC-20** (appears under both Kevalavata and general vata-vyadhi groupings) |
| Jvara | Fever | **EC-3** |
| Panduroga | Anemia | **EC-5** |
| Vibandha | Constipation | **AAC-12.4** |
| Agnimandya/Agnisada | Sluggish digestion | **DB-1** |
| Arsha | Hemorrhoids | (listed among top-10 most-recorded OPD codes nationally, exact sub-code not confirmed here) |
| Kushtha | Skin disease | (top-10 recorded category; exact code not confirmed here — verify on portal) |

**Note on Prameha/Madhumeha (diabetes) and Katishula (lumbar spondylosis)**: these are extremely common OPD presentations and definitely have NAMASTE entries, but I could not confirm their exact alphanumeric codes from available published sources — pull these directly from the live NAMASTE portal search rather than guessing.

### What's solid vs. what needs portal verification
- **Solid**: the overall two-system structure (NAMASTE = India's Ayurveda/Siddha/Unani terminology+morbidity codes; ICD-11 Chapter 26 TM2 = WHO's international traditional-medicine module, officially released on the ICD-11 Browser Feb 2025), the double-coding requirement for AYUSH insurance/EHR compliance (A-HMIS), and the general condition list (Sandhivata, Amavata, Amlapitta, Tamaka Shwasa, Prameha, Gridhrasi, Grahani Dosha, Vatarakta, Katishula, Kushtha are all genuinely common, classically-named OPD presentations).
- **Needs live verification before you hardcode anything**: exact code strings. Codes are actively being expanded/mapped (the 1,941-code mapping milestone was only finalized this year), so treat the portal/ICD-11 Browser as the single source of truth, not any static table (including this one).
- **Formulations** (Yogaraja Guggulu, Maharasnadi Kwath, Avipattikara Churna, Chandraprabha Vati, etc.) listed in the original planning doc are all real, commonly-used classical formulations for their respective conditions and are reasonable to keep as reference — just don't present them as prescriptive/dosing advice in the LLM output, since the task's own constraint says the system must never prescribe.

---

## 4. Red-Flag Emergency Triage Criteria

### 4.1 Allopathic red flags (standard, well-established clinical criteria — safe to hardcode as reference)
- **Acute coronary syndrome / MI**: acute chest pain, especially with radiation to left arm/jaw/back, associated cold sweats, nausea, or breathlessness.
- **Stroke (FAST)**: sudden unilateral facial drooping, arm/leg weakness, slurred or difficult speech, sudden onset.
- **Respiratory failure**: acute severe dyspnea, stridor, inability to speak full sentences, cyanosis.
- **GI hemorrhage / acute abdomen**: hematemesis, melena, rigid/board-like abdomen, severe unremitting abdominal pain.
- **Meningitis/sepsis**: high fever with neck stiffness, altered consciousness/sensorium, photophobia, non-blanching rash.

These are standard, universally-taught emergency medicine red flags (not something that changes by region or needs live sourcing) — safe to use directly as your CONSTRAINTS/reference logic for the SOCRATES module's `red_flags` field.

### 4.2 Ayurvedic red flags — Arishta Lakshana (classical mortality/severity indicators)
Classical texts (Charaka Samhita Indriya Sthana, Sushruta Samhita Sutra Sthana, and especially Ashtanga Sangraha Shareera Sthana Ch. 11 "Vikruta Vyadhi Vignaneeyam") describe **Arishta Lakshana** — clusters of signs indicating a grave/fatal prognosis, historically used by Vaidyas to recognize when a condition has moved beyond manageable and needs urgent/emergency intervention. Examples directly relevant to your red-flag list:

- **Sannipata Jwara with delirium** — fever with all three doshas involved, altered mental status; classical descriptions of this condition have been directly compared in recent literature to modern **sepsis/SIRS/septic shock with delirium** — a recognized emergency correlate.
- **Acute Hridroga (heart disease) with collapse** — Ayurveda's Sannipataja/severe Hridroga descriptions include chest heaviness, giddiness, syncope, nausea and acute chest pain together — explicitly flagged in Ayurvedic literature as needing immediate active management, correlating to angina/MI presentations.
- **Severe Atisara (diarrhea) with dehydration/collapse** — classical texts describe Atisara as rapidly depleting bodily strength and potentially fatal if untreated, which correlates clinically to hypovolemic shock from severe dehydration.
- **Shwasa (breathlessness) described as life-threatening if untreated** — classical texts (Charaka Chikitsa Sthana) explicitly flag severe Shwasa as a "Pranahara" (life-threatening) condition.
- Broader classical categories worth knowing for context: conditions termed **Atyayika Vyadhi** (emergency disease), **Daruna Vyadhi** (severe/grave disease), and disease phases termed **Vega** (acute exacerbation) — these are the classical Ayurvedic conceptual equivalents of "this needs urgent/emergency handling now," useful framing if you want your Vikriti/red-flag prompt to explain *why* it's escalating in Ayurveda-consistent language rather than just borrowing allopathic terms.

**Practical takeaway for your prompt**: when Vikriti conversation surfaces a cluster matching any of the above (e.g., patient reports chest pain + heaviness + giddiness, or high fever + confusion, or profuse diarrhea + weakness/collapse symptoms), your system prompt's CONSTRAINTS section should treat it the same way the SOCRATES module treats red flags — stop the normal flow and escalate/refer to allopathic emergency care rather than continuing dosha-scoring questions. This mirrors real Ayurvedic clinical practice, where Vaidyas are trained to recognize Arishta Lakshana as a signal to refer out, not treat in-house.

---

## 5. SOCRATES Framework — the 8 Axes (for Module B)

Standard, universally-taught clinical mnemonic (UK/Commonwealth medical curricula; used identically in MBBS training) — this is stable, well-established content, safe to hardcode:

| Letter | Axis | What it captures | Example prompt |
|---|---|---|---|
| **S** | Site | Exact location of the symptom | "Where exactly is the pain?" |
| **O** | Onset | Sudden vs. gradual, when it started | "When did it start — suddenly or gradually?" |
| **C** | Character | Quality/nature of the symptom | "Is it sharp, dull, burning, throbbing?" |
| **R** | Radiation | Does it spread/move elsewhere | "Does it move anywhere else?" |
| **A** | Associated symptoms | What else accompanies it | "Anything else alongside this?" |
| **T** | Time course | Constant, intermittent, changing pattern | "Is it constant or does it come and go?" |
| **E** | Exacerbating/relieving factors | What makes it better/worse | "Does anything make it better or worse?" |
| **S** | Severity | Usually 1–10 scale | "On a scale of 1–10, how severe?" |

A few practically useful notes for your prompt design:
- SOCRATES is meant to be used as a **flexible checklist, not a rigid script** — real clinicians ask in whatever order fits the patient's narrative and skip an axis if the patient already answered it unprompted. Your system prompt's existing instruction ("in whatever order fits the conversation... do not ask about an axis already covered") is exactly aligned with how this framework is actually taught and used.
- Not every axis applies equally to every symptom (e.g., "Radiation" is often not meaningful for a rash or for shortness of breath) — your prompt could optionally allow the LLM to skip an axis if it's clinically inapplicable to the presenting symptom, rather than forcing all eight.
- SOCRATES covers the **History of Presenting Complaint** specifically — it's *not* the whole clinical history (past medical history, medications, allergies aren't part of it). That's consistent with your system's scope (structured symptom history only, no diagnosis).

---

## 6. Notes for Persona/Test-Transcript Design (Step A4/B2 testing)

The task sheet asks you to role-play 4–5 test patients yourself rather than use pre-scripted transcripts, which is the right approach for two reasons worth noting in your documentation:
1. **Copyright/originality**: pre-existing "doctor-patient dialogue transcripts" online are typically from published case studies, textbooks, or OSCE training materials — reusing those verbatim isn't appropriate for a submission; role-playing your own is both cleaner and better for actually stress-testing your specific prompt.
2. **Testing value**: the four persona types described in the original planning notes (emergency red-flag / allopathic SOCRATES / Ayurvedic CCRAS-PAS + Vikriti / integrative mixed-mode diabetic-with-Ayurvedic-symptoms) map well onto the checklist items already in your task sheet — specifically the two tests that matter most: (a) a patient-history chunk that should change urgency (e.g., chest pain + documented prior MI/heart attack), and (b) an empty patient-history scenario (new patient) to confirm nothing breaks. Structure your 4–5 role-played patients around those two test conditions plus one red-flag case and one straightforward chronic-symptom case for each module.

---

## Sources Consulted
- CCRAS / Journal of Research in Ayurvedic Sciences — Prakriti Assessment Scale, Ayur Prakriti web portal
- Academia.edu / ResearchGate — "Development of a Standardized Prakriti Assessment Tool," multiple validation studies
- Frontiers in Medicine (2025) — critical review of 64 Prakriti assessment tools
- IJLPR, JAIMS, IJAPR, EasyAyurveda — Sattva Pariksha classification (Pravara/Madhyama/Avara)
- Ayurvaid.com, ResearchGate — Dashavidha Pariksha overview articles
- International Journal of Ayurveda Research (2025) — India's roadmap for ICD-11 TM2 implementation
- Journal of Research in Ayurvedic Sciences — NAMASTE portal data analysis (real code list)
- GitHub (NAMASTE-ICD-11-Integration) — coding scheme structure overview
- Geeky Medics, ClinicalBridge, Skills Training Group — SOCRATES framework
- AYUSCRIPT, MedCrave, ResearchGate — Arishta Lakshana / Ayurvedic emergency concepts (Atyayika Chikitsa), Sama Sannipata Jwara–sepsis correlation, Hridroga emergency correlation

*All classical/clinical content above is paraphrased and summarized from the sources listed; verify exact NAMASTE/ICD-11 codes against the live portal before hardcoding into your lookup table, since these are still being expanded.*
