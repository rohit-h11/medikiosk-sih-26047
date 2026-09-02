# Dialogue Management & SOCRATES Engine Package
from app.ai.dialogue.controller import DialogueController
from app.ai.dialogue.red_flags import (
    scan_text_for_red_flags,
    evaluate_patient_safety,
    RED_FLAG_RULES
)
from app.ai.dialogue.ccras_pas import (
    load_ccras_battery,
    get_all_battery_questions,
    get_representative_ccras_questions,
    compute_prakriti_scores,
    convert_ccras_question_to_touch_options,
    classify_agni_koshtha_from_text,
    detect_ayurvedic_vikriti
)
from app.ai.dialogue.dashavidha import (
    SATMYA_QUESTIONNAIRE,
    SATTVA_QUESTIONNAIRE,
    VYAYAMA_QUESTIONNAIRE,
    score_satmya_assessment,
    score_sattva_assessment,
    score_vyayama_assessment,
    classify_vaya_lifestage,
    EXCLUDED_PHYSICAL_EXAM_PARAMETERS
)
from app.ai.dialogue.llm_engine import (
    extract_socrates_slots,
    generate_heuristic_next_turn,
    generate_dialogue_turn_llm,
    build_vikriti_system_prompt,
    build_socrates_system_prompt
)
from app.ai.dialogue.session_store import (
    create_session,
    get_session,
    save_session,
    delete_session,
    list_active_sessions
)
from app.ai.dialogue.namaste_bridge import (
    search_namaste_codes,
    get_namaste_item_by_code,
    NamasteDiagnosisItem,
    NAMASTE_DATABASE
)
from app.ai.dialogue.fhir_adapter import convert_dialogue_to_fhir_r4

__all__ = [
    "DialogueController",
    "scan_text_for_red_flags",
    "evaluate_patient_safety",
    "RED_FLAG_RULES",
    "load_ccras_battery",
    "get_all_battery_questions",
    "get_representative_ccras_questions",
    "compute_prakriti_scores",
    "convert_ccras_question_to_touch_options",
    "classify_agni_koshtha_from_text",
    "detect_ayurvedic_vikriti",
    "SATMYA_QUESTIONNAIRE",
    "SATTVA_QUESTIONNAIRE",
    "VYAYAMA_QUESTIONNAIRE",
    "score_satmya_assessment",
    "score_sattva_assessment",
    "score_vyayama_assessment",
    "classify_vaya_lifestage",
    "EXCLUDED_PHYSICAL_EXAM_PARAMETERS",
    "extract_socrates_slots",
    "generate_heuristic_next_turn",
    "generate_dialogue_turn_llm",
    "build_vikriti_system_prompt",
    "build_socrates_system_prompt",
    "create_session",
    "get_session",
    "save_session",
    "delete_session",
    "list_active_sessions",
    "search_namaste_codes",
    "get_namaste_item_by_code",
    "NamasteDiagnosisItem",
    "NAMASTE_DATABASE",
    "convert_dialogue_to_fhir_r4"
]
