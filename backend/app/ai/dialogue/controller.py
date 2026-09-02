from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.schemas.dialogue import (
    HistoryType,
    InterviewPhase,
    DialogueStartRequest,
    DialogueTurnInput,
    DialogueTurnResponse,
    DialogueTurn,
    DialogueSessionState,
    RedFlagAlert,
    TouchOption,
    AyurvedicAssessment
)
from app.ai.dialogue.session_store import (
    create_session,
    get_session,
    save_session
)
from app.ai.dialogue.red_flags import evaluate_patient_safety
from app.ai.dialogue.ccras_pas import (
    compute_prakriti_scores,
    classify_agni_koshtha_from_text,
    detect_ayurvedic_vikriti,
    get_representative_ccras_questions
)
from app.ai.dialogue.dashavidha import (
    classify_vaya_lifestage,
    score_satmya_assessment,
    score_sattva_assessment,
    score_vyayama_assessment,
    SATMYA_QUESTIONNAIRE,
    SATTVA_QUESTIONNAIRE,
    VYAYAMA_QUESTIONNAIRE
)
from app.ai.dialogue.llm_engine import (
    extract_socrates_slots,
    generate_dialogue_turn_llm
)

class DialogueController:
    """
    Core Controller managing SOCRATES adaptive branching, AYUSH CCRAS-PAS intake,
    and Mixed Integrative Care. Enforces turn limits (6-8 turns max) and <3 minute patient interview constraints.
    """

    @classmethod
    async def start_session(cls, req: DialogueStartRequest) -> DialogueTurnResponse:
        """Initialize a new clinical intake session."""
        session = create_session(
            patient_id=req.patient_id,
            history_type=req.history_type,
            language=req.language,
            extracted_document_context=req.extracted_document_context
        )
        session.primary_framework = req.primary_framework or req.history_type
        session.clinical_reference_chunks = req.clinical_reference_chunks or []
        session.patient_history_chunks = req.patient_history_chunks or []
        session.age = req.age

        # Classify Vaya life stage if age provided
        if req.age is not None:
            if not session.clinical_history.ayurvedic_assessment:
                session.clinical_history.ayurvedic_assessment = AyurvedicAssessment()
            session.clinical_history.ayurvedic_assessment.vaya_lifestage = classify_vaya_lifestage(req.age)

        # Check for immediate red flag in chief complaint hint or history chunks
        red_flag = None
        if req.chief_complaint_hint:
            red_flag = evaluate_patient_safety(
                current_utterance=req.chief_complaint_hint,
                cumulative_transcript=[],
                patient_history_chunks=session.patient_history_chunks
            )
            if red_flag:
                session.active_red_flag = red_flag
                session.phase = InterviewPhase.RED_FLAG_TRIAGE
                session.is_completed = True
                session.clinical_history.red_flags.append(red_flag)
                save_session(session)
                return cls._build_red_flag_response(session, red_flag)

        # Generate initial welcoming & chief complaint question
        q_text, touch_opts, next_phase, cue = await generate_dialogue_turn_llm(
            history_type=session.history_type,
            phase=session.phase,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
            transcript=[],
            socrates=session.clinical_history.standard_history.socrates,
            ayurvedic=session.clinical_history.ayurvedic_assessment,
            extracted_docs=session.extracted_document_context,
            clinical_reference_chunks=session.clinical_reference_chunks,
            patient_history_chunks=session.patient_history_chunks,
            ccras_battery_index=session.ccras_battery_index
        )

        # Record AI turn
        session.turns.append(
            DialogueTurn(
                turn_number=1,
                speaker="ai",
                utterance=q_text,
                phase=session.phase
            )
        )
        session.turn_count = 1
        save_session(session)

        return DialogueTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            max_turns=session.max_turns,
            phase=session.phase,
            question_text=q_text,
            touch_options=touch_opts,
            red_flag_alert=None,
            is_completed=False,
            progress_percentage=round((1 / session.max_turns) * 100, 1),
            clinical_history=session.clinical_history,
            audio_guidance_cue=cue
        )

    @classmethod
    async def process_turn(cls, inp: DialogueTurnInput) -> DialogueTurnResponse:
        """
        Process a patient's response (speech transcript or touch selection)
        and formulate the next logical clinical follow-up question.
        """
        session = get_session(inp.session_id)
        if not session:
            raise ValueError(f"Dialogue session '{inp.session_id}' not found.")

        # Update RAG chunks if passed per turn
        if inp.clinical_reference_chunks:
            session.clinical_reference_chunks = inp.clinical_reference_chunks
        if inp.patient_history_chunks:
            session.patient_history_chunks = inp.patient_history_chunks

        # If already completed or in red-flag triage, return terminal state
        if session.is_completed and session.active_red_flag:
            return cls._build_red_flag_response(session, session.active_red_flag)

        if session.is_completed:
            return cls._build_completed_response(session)

        # 1. Deterministic Red-Flag Safety Evaluation (<5ms)
        past_patient_utterances = [t.utterance for t in session.turns if t.speaker == "patient"]
        red_flag = evaluate_patient_safety(
            current_utterance=inp.patient_response,
            cumulative_transcript=past_patient_utterances,
            patient_history_chunks=session.patient_history_chunks
        )
        
        if red_flag:
            session.active_red_flag = red_flag
            session.phase = InterviewPhase.RED_FLAG_TRIAGE
            session.is_completed = True
            session.clinical_history.red_flags.append(red_flag)
            session.clinical_history.completed_at = datetime.now(timezone.utc).isoformat()
            
            # Record patient turn
            session.turns.append(
                DialogueTurn(
                    turn_number=session.turn_count + 1,
                    speaker="patient",
                    utterance=inp.patient_response,
                    selected_option_id=inp.selected_option_id,
                    phase=InterviewPhase.RED_FLAG_TRIAGE
                )
            )
            save_session(session)
            return cls._build_red_flag_response(session, red_flag)

        # 2. Record Patient Utterance
        session.turns.append(
            DialogueTurn(
                turn_number=session.turn_count + 1,
                speaker="patient",
                utterance=inp.patient_response,
                selected_option_id=inp.selected_option_id,
                phase=session.phase
            )
        )

        # 3. Clinical Data Extraction & State Evolution
        cls._update_clinical_state(session, inp.patient_response, inp.selected_option_id)

        # 4. Turn Count & Completion Check
        session.turn_count += 1
        is_last_turn = session.turn_count >= session.max_turns

        # 5. Formulate Next Question via LLM / Heuristic Engine
        transcript_history = [{"role": t.speaker, "content": t.utterance} for t in session.turns]
        
        q_text, touch_opts, next_phase, cue = await generate_dialogue_turn_llm(
            history_type=session.history_type,
            phase=session.phase,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
            transcript=transcript_history,
            socrates=session.clinical_history.standard_history.socrates,
            ayurvedic=session.clinical_history.ayurvedic_assessment,
            extracted_docs=session.extracted_document_context,
            clinical_reference_chunks=session.clinical_reference_chunks,
            patient_history_chunks=session.patient_history_chunks,
            ccras_battery_index=session.ccras_battery_index
        )

        session.phase = next_phase

        if is_last_turn or next_phase == InterviewPhase.COMPLETED:
            session.is_completed = True
            session.phase = InterviewPhase.COMPLETED
            session.clinical_history.completed_at = datetime.now(timezone.utc).isoformat()

        # Record AI turn
        session.turns.append(
            DialogueTurn(
                turn_number=session.turn_count + 1,
                speaker="ai",
                utterance=q_text,
                phase=session.phase
            )
        )
        session.turn_count += 1
        save_session(session)

        progress = 100.0 if session.is_completed else round(min(95.0, (session.turn_count / session.max_turns) * 100), 1)

        return DialogueTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            max_turns=session.max_turns,
            phase=session.phase,
            question_text=q_text,
            touch_options=touch_opts,
            red_flag_alert=None,
            is_completed=session.is_completed,
            progress_percentage=progress,
            clinical_history=session.clinical_history,
            audio_guidance_cue=cue
        )

    @classmethod
    def _update_clinical_state(
        cls,
        session: DialogueSessionState,
        patient_text: str,
        selected_option_id: Optional[str]
    ) -> None:
        """Update SOCRATES slots, CCRAS-PAS dosha scores, or Dashavidha Pariksha."""
        std_hist = session.clinical_history.standard_history

        # Initial Chief Complaint extraction
        if not std_hist.chief_complaint:
            std_hist.chief_complaint = patient_text
            std_hist.hpi = f"Patient presents with: {patient_text}."

        if session.history_type in (HistoryType.ALLOPATHIC, HistoryType.MIXED):
            # SOCRATES extraction
            std_hist.socrates = extract_socrates_slots(patient_text, std_hist.socrates)
            
            # Check for medication or allergy mentions
            text_lower = patient_text.lower()
            if "allerg" in text_lower and not std_hist.known_allergies:
                std_hist.known_allergies.append(patient_text)
            if any(k in text_lower for k in ["taking", "medication", "tablet", "capsule", "dosage"]) and not std_hist.current_medications:
                std_hist.current_medications.append(patient_text)
            if any(k in text_lower for k in ["diabetes", "hypertension", "thyroid", "asthma", "bp"]):
                if patient_text not in std_hist.past_medical_history:
                    std_hist.past_medical_history.append(patient_text)

        if session.history_type in (HistoryType.AYURVEDIC, HistoryType.MIXED):
            ayur = session.clinical_history.ayurvedic_assessment
            if not ayur:
                ayur = session.clinical_history.ayurvedic_assessment = AyurvedicAssessment()

            # Vikriti Detection
            if not ayur.vikriti:
                ayur.vikriti = detect_ayurvedic_vikriti(std_hist.chief_complaint or "", [patient_text])

            # CCRAS-PAS Answer Tracking
            if session.phase == InterviewPhase.CCRAS_PRAKRITI:
                rep_questions = get_representative_ccras_questions(max_count=4)
                if session.ccras_battery_index < len(rep_questions):
                    active_q = rep_questions[session.ccras_battery_index]
                    d_id = active_q.get("domain_id", "physical")
                    
                    # Match selected option or text
                    selected_dosha = "vata"
                    if selected_option_id == "opt_p" or "pitta" in patient_text.lower() or "sharp" in patient_text.lower() or "medium" in patient_text.lower():
                        selected_dosha = "pitta"
                    elif selected_option_id == "opt_k" or "kapha" in patient_text.lower() or "broad" in patient_text.lower() or "heavy" in patient_text.lower():
                        selected_dosha = "kapha"
                    
                    session.prakriti_raw_answers.append({
                        "domain_id": d_id,
                        "dosha": selected_dosha,
                        "weight": 1.0
                    })
                    
                    ayur.prakriti = compute_prakriti_scores(session.prakriti_raw_answers)
                    session.ccras_battery_index += 1

            # Dashavidha Pariksha (Agni, Koshtha, Ahara-Vihara)
            agni, koshtha = classify_agni_koshtha_from_text(patient_text)
            if agni and not ayur.agni:
                ayur.agni = agni
            if koshtha and not ayur.koshtha:
                ayur.koshtha = koshtha
            if (session.phase in (InterviewPhase.AYURVEDIC_PARIKSHA, InterviewPhase.COMPLETED) or
                any(k in patient_text.lower() for k in ["meal", "stress", "diet", "sleep", "lifestyle", "eating", "food"]) or
                (selected_option_id and selected_option_id.startswith("av_"))):
                if not ayur.ahara_vihara:
                    ayur.ahara_vihara = patient_text

    @classmethod
    def _build_red_flag_response(
        cls,
        session: DialogueSessionState,
        alert: RedFlagAlert
    ) -> DialogueTurnResponse:
        """Format an immediate emergency triage override response."""
        return DialogueTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            max_turns=session.max_turns,
            phase=InterviewPhase.RED_FLAG_TRIAGE,
            question_text=f"⚠️ MEDICAL EMERGENCY DETECTED: {alert.emergency_message} Please report immediately to: {alert.triage_destination}.",
            touch_options=[
                TouchOption(
                    id="opt_emergency_ack",
                    label="I understand — Alert Casualty Staff",
                    value="Emergency acknowledged",
                    slot_tag="emergency_ack"
                )
            ],
            red_flag_alert=alert,
            is_completed=True,
            progress_percentage=100.0,
            clinical_history=session.clinical_history,
            audio_guidance_cue="Emergency protocol activated. Hospital casualty staff have been notified."
        )

    @classmethod
    def _build_completed_response(
        cls,
        session: DialogueSessionState
    ) -> DialogueTurnResponse:
        """Format a session already completed response."""
        return DialogueTurnResponse(
            session_id=session.session_id,
            turn_number=session.turn_count,
            max_turns=session.max_turns,
            phase=InterviewPhase.COMPLETED,
            question_text="Your clinical history intake is already complete. Summary has been saved for the doctor.",
            touch_options=[],
            red_flag_alert=session.active_red_flag,
            is_completed=True,
            progress_percentage=100.0,
            clinical_history=session.clinical_history,
            audio_guidance_cue="Interview finished. Thank you."
        )
