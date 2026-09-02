# MediKiosk — RAG ↔ Prompt Engineering Interface Spec

What the RAG teammate needs to build, and exactly what the prompt-engineering teammate needs from it — so both sides build to the same contract.

---

## The big picture

Every LLM call in our history-taking flow needs three inputs: server instructions (owned by prompt engineering), what the patient said (the transcript), and retrieved reference chunks (owned by RAG). This document is about that third input — what needs to be retrievable, from where, and in what shape.

There are **THREE separate collections** needed, not one shared knowledge base. Two are static (same for every patient), one is dynamic (specific to the one patient in front of you). Mixing them causes real bugs — e.g. a chest-pain question accidentally retrieving a NAMASTE diagnosis code instead of a red-flag warning. Keep them as separate collections/namespaces in the vector DB.

---

## Collection 1 — Clinical Reference (static)

Used during questioning, by BOTH the Vikriti (Ayurveda) and SOCRATES (Allopathy) prompts. Same content for every patient — this doesn't change per person.

**What's in it**
- Symptom-to-dosha table — which symptoms indicate Vata / Pitta / Kapha aggravation (e.g. dryness, constipation, anxiety → Vata; burning, acidity, irritability → Pitta; heaviness, congestion, lethargy → Kapha).
- SOCRATES red-flag list — symptom combinations that mean "escalate immediately" (e.g. chest pain radiating to the arm, sudden severe headache).
- Symptom-to-differential context — general clinical background per symptom, for grounding follow-up questions (not for diagnosing).

**Where to source it from**
- Ayurveda table: CCRAS publications, classical texts (Charaka Samhita, Ashtanga Hridaya). Since our PS is from AIIA, check first whether the hackathon gives us access to an AYUSH/Ayurveda mentor — a validated table from them beats compiling one from scattered sources under time pressure.
- SOCRATES red-flags/differentials: standard MBBS clinical references (Macleod's Clinical Examination, Bates' Guide) or public guidelines (NICE, WHO red-flag symptom lists).

**RAG owns:** sourcing this content, chunking it, embedding it, and retrieving the top relevant chunks based on the patient's current statement (e.g. patient says "chest pain" → retrieve chest-pain-specific red flags and relevant SOCRATES axes, not the entire table).

---

## Collection 2 — NAMASTE Coding (static)

Used ONCE, at the end — not during questioning. When the doctor's final Ayurvedic diagnosis needs to be converted into a standardized code for FHIR export.

**What's in it**
- NAMASTE terminology entries — code + description pairs from the Ministry of AYUSH's standardized morbidity codes for Ayurveda/Siddha/Unani.

**Where to source it from**
- Official portal: namaste.ayush.gov.in (legacy endpoint: namstp.ayush.gov.in).
- Check the PS 26047 problem statement packet first — SIH-style problem statements often ship a sample NAMASTE dataset (CSV) directly, which would save scraping the portal.

**RAG owns:** embedding the NAMASTE entries so that a free-text diagnosis (e.g. "Vata-Pradhana Sandhivata") can be semantically matched to its official code, rather than requiring an exact string match. This is a separate retrieval call, made once per consultation, not per question.

---

## Collection 3 — Patient History (dynamic, per-patient)

This is different from the other two — it's not general knowledge, it's THIS patient's own past documents/conversations. Filtered to one patient ID at a time. This is the same store already planned for the doctor's ad-hoc Q&A feature; it should also feed the LIVE questioning prompt, not just the doctor's later lookup.

**Why this matters:** if a patient says "chest pain" and they have a documented prior heart attack, that history has to reach the prompt at question-time, not just be available for the doctor to find later. Missing this kind of context during live questioning is a real safety gap, not just a nice-to-have.

**RAG owns:** retrieving relevant chunks from this specific patient's history based on their current statement, scoped strictly to that patient's own records (never another patient's).

---

## The handoff: what RAG passes to the prompt

For every question-turn during Vikriti or SOCRATES, RAG runs retrieval against the patient's latest statement and returns chunks from the relevant collections. Suggested shape for the handoff:

```json
{
  "clinical_reference_chunks": [
    { "text": "...", "source": "symptom_dosha_table" }
  ],
  "patient_history_chunks": [
    { "text": "...", "date": "...", "source": "past_visit_note" }
  ]
}
```

NAMASTE retrieval is separate and only called once, at diagnosis-coding time — it doesn't appear in the per-question handoff above.

**Prompt engineering owns:** writing the system prompt so it uses BOTH chunk types correctly — general clinical knowledge should inform what to ask next; patient history should raise urgency/context (e.g. treat a positive prior-MI history as reason to flag urgency sooner, not just note it). Confirm the exact JSON shape with RAG before building against it — this doc is a starting proposal, not a final schema.

---

## Sync checklist for both of you

- [ ] Agree on the exact chunk-handoff format (field names, chunk size) before either side builds against it.
- [ ] RAG: clinical reference collection embedded and retrievable by symptom keyword.
- [ ] RAG: NAMASTE collection embedded and retrievable by free-text diagnosis description.
- [ ] RAG: patient-history retrieval scoped correctly per patient (test this — a leak across patients is a serious bug, not a minor one).
- [ ] Prompt engineering: system prompts written to handle the case where patient-history chunks are empty (new patient, no prior records) without breaking.
- [ ] Both: test end-to-end with at least one scenario where patient history should change the outcome (like the chest-pain + prior-MI case) to confirm it actually reaches the prompt.
