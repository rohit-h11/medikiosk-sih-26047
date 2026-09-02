import pytest
from app.schemas.dialogue import (
    HistoryType,
    InterviewPhase,
    DialogueStartRequest,
    DialogueTurnInput,
    SocratesState,
    RedFlagSeverity
)
from app.ai.dialogue import (
    DialogueController,
    scan_text_for_red_flags,
    load_ccras_battery,
    get_representative_ccras_questions,
    compute_prakriti_scores,
    classify_agni_koshtha_from_text,
    detect_ayurvedic_vikriti,
    extract_socrates_slots,
    get_session
)

# -------------------------------------------------------------
# 1. Red-Flag Emergency Triage Tests
# -------------------------------------------------------------

def test_red_flag_detection_cardiovascular():
    """Verify crushing chest pain radiating to left arm triggers CRITICAL red flag."""
    text = "I have sudden crushing chest pain radiating to my left arm with cold sweating"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == RedFlagSeverity.CRITICAL
    assert "Cardiovascular" in alert.category
    assert "left arm" in alert.triggers[0].lower() or "chest pain" in alert.triggers[0].lower()

def test_red_flag_detection_stroke_fast():
    """Verify facial droop and slurred speech triggers CRITICAL stroke alert."""
    text = "My mother has sudden facial droop and slurred speech since 30 minutes ago"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == RedFlagSeverity.CRITICAL
    assert "Cerebrovascular" in alert.category

def test_red_flag_detection_hemorrhage():
    """Verify vomiting blood triggers HIGH priority alert."""
    text = "I am vomiting blood and having black tarry stool"
    alert = scan_text_for_red_flags(text)
    assert alert is not None
    assert alert.is_red_flag is True
    assert alert.severity == RedFlagSeverity.HIGH
    assert "Hemorrhage" in alert.category

def test_red_flag_negative_routine_complaint():
    """Verify routine non-emergency complaint does not trigger red flags."""
    text = "I have mild knee pain when climbing stairs for the past 2 weeks"
    alert = scan_text_for_red_flags(text)
    assert alert is None

# -------------------------------------------------------------
# 2. CCRAS-PAS Battery & Scoring Tests
# -------------------------------------------------------------

def test_ccras_battery_loading():
    """Verify CCRAS-PAS question battery loads with all 4 validated domains."""
    data = load_ccras_battery()
    domains = [d["domain_id"] for d in data.get("domains", [])]
    assert "physical" in domains
    assert "physiological" in domains
    assert "psychological" in domains
    assert "behavioral" in domains
    
    rep = get_representative_ccras_questions(max_count=4)
    assert len(rep) == 4

def test_prakriti_scoring_vata_dominant():
    """Verify dominant Vata answers compute Ekadoshaja Vata phenotype."""
    answers = [
        {"domain_id": "physical", "dosha": "vata", "weight": 1.0},
        {"domain_id": "physiological", "dosha": "vata", "weight": 1.0},
        {"domain_id": "psychological", "dosha": "vata", "weight": 1.0},
        {"domain_id": "behavioral", "dosha": "pitta", "weight": 1.0}
    ]
    scores = compute_prakriti_scores(answers)
    assert scores.vata_percentage == 75.0
    assert scores.pitta_percentage == 25.0
    assert scores.kapha_percentage == 0.0
    assert "Vata Dominant" in scores.dominant_prakriti
    assert scores.phenotype_type == "Ekadoshaja"

def test_prakriti_scoring_dvandvaja_vata_pitta():
    """Verify mixed answers compute Dvandvaja (dual dosha) phenotype."""
    answers = [
        {"domain_id": "physical", "dosha": "vata", "weight": 1.0},
        {"domain_id": "physiological", "dosha": "pitta", "weight": 1.0},
        {"domain_id": "psychological", "dosha": "vata", "weight": 1.0},
        {"domain_id": "behavioral", "dosha": "pitta", "weight": 1.0}
    ]
    scores = compute_prakriti_scores(answers)
    assert scores.vata_percentage == 50.0
    assert scores.pitta_percentage == 50.0
    assert "Vata-Pitta" in scores.dominant_prakriti
    assert scores.phenotype_type == "Dvandvaja"

def test_agni_and_koshtha_classification():
    """Verify Dashavidha Pariksha Agni/Koshtha extraction."""
    agni, koshtha = classify_agni_koshtha_from_text("I have sharp hunger and acid burning with soft stool")
    assert agni is not None and "Tikshna" in agni
    assert koshtha is not None and "Mridu" in koshtha

    agni2, koshtha2 = classify_agni_koshtha_from_text("I have irregular hunger, gas, and hard stool with constipation")
    assert agni2 is not None and "Vishama" in agni2
    assert koshtha2 is not None and "Krura" in koshtha2

def test_ayurvedic_vikriti_detection():
    """Verify Vikriti detector identifies dosha imbalance."""
    vikriti = detect_ayurvedic_vikriti("Severe joint pain and body stiffness", ["dryness", "numbness"])
    assert "Vataja" in vikriti

# -------------------------------------------------------------
# 3. SOCRATES Extraction & Slot Filling Tests
# -------------------------------------------------------------

def test_socrates_slot_extraction():
    """Verify SOCRATES slot extraction from natural language."""
    state = SocratesState()
    
    # 1. Site & Onset
    s1 = extract_socrates_slots("I have severe right knee pain since 3 weeks", state)
    assert s1.site == "Knee"
    assert "3 weeks" in s1.onset
    assert "site" not in s1.missing_slots
    assert "onset" not in s1.missing_slots

    # 2. Character & Severity
    s2 = extract_socrates_slots("It is a dull aching sensation rated 7 out of 10", s1)
    assert s2.character == "Dull"
    assert s2.severity_score == 7
    assert "character" not in s2.missing_slots
    assert "severity" not in s2.missing_slots

    # 3. Radiation & Timecourse
    s3 = extract_socrates_slots("It stays in one place, localized, but is continuous all day", s2)
    assert "Localized" in s3.radiation
    assert "Constant" in s3.time_course

# -------------------------------------------------------------
# 4. End-to-End Dialogue Controller Simulations
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_allopathic_dialogue_simulation():
    """Simulate complete 5-turn Allopathic SOCRATES intake."""
    req = DialogueStartRequest(
        patient_id="PAT_ALLO_001",
        history_type=HistoryType.ALLOPATHIC,
        language="en"
    )
    # Turn 1: Start
    r1 = await DialogueController.start_session(req)
    assert r1.session_id is not None
    assert r1.turn_number == 1
    assert r1.is_completed is False
    assert len(r1.touch_options) > 0

    # Turn 2: Chief Complaint
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have severe right knee pain since 2 weeks",
            selected_option_id="cc_pain"
        )
    )
    assert r2.clinical_history.standard_history.chief_complaint is not None
    assert r2.clinical_history.standard_history.socrates.site == "Knee"

    # Turn 3: Character & Severity
    r3 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="It is a dull, constant ache rated 6 out of 10",
            selected_option_id="char_dull"
        )
    )
    assert r3.clinical_history.standard_history.socrates.severity_score == 6

    # Turn 4: Factors
    r4 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="It gets worse with movement and improves with rest",
            selected_option_id="factor_move"
        )
    )
    assert r4.clinical_history.standard_history.socrates.exacerbating_relieving is not None

    # Turn 5: Past Medical & Completion
    r5 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have a history of hypertension and take Amlodipine 5mg",
            selected_option_id="bg_htn_dm"
        )
    )
    assert r5.is_completed is True
    assert r5.progress_percentage == 100.0

@pytest.mark.asyncio
async def test_ayurvedic_dialogue_simulation():
    """Simulate complete Ayurvedic CCRAS-PAS + Dashavidha Pariksha intake."""
    req = DialogueStartRequest(
        patient_id="PAT_AYUR_002",
        history_type=HistoryType.AYURVEDIC,
        language="en"
    )
    # Turn 1: Start
    r1 = await DialogueController.start_session(req)
    assert r1.session_id is not None
    assert r1.phase == InterviewPhase.CHIEF_COMPLAINT

    # Turn 2: Chief Complaint / Vikriti
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have severe joint stiffness, bodyache and dry skin",
            selected_option_id="ay_joint"
        )
    )
    assert r2.clinical_history.ayurvedic_assessment.vikriti is not None
    assert "Vataja" in r2.clinical_history.ayurvedic_assessment.vikriti

    # Turn 3: CCRAS Domain 1 (Physical - Body frame)
    r3 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="Lean / Slender build with difficulty gaining weight",
            selected_option_id="opt_v"
        )
    )
    assert r3.clinical_history.ayurvedic_assessment.prakriti is not None

    # Turn 4: CCRAS Domain 2 (Physiological - Agni/Appetite)
    r4 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="Variable & Irregular hunger (Vishama Agni)",
            selected_option_id="opt_v"
        )
    )
    assert r4.clinical_history.ayurvedic_assessment.prakriti.vata_percentage > 0

    # Turn 5: Dashavidha Pariksha (Ahara-Vihara)
    r5 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="Irregular meal timings, high work stress and late night sleep",
            selected_option_id="av_irregular"
        )
    )
    assert r5.clinical_history.ayurvedic_assessment.ahara_vihara is not None

@pytest.mark.asyncio
async def test_emergency_red_flag_interview_override():
    """Verify acute chest pain in mid-interview immediately halts interview and triages."""
    req = DialogueStartRequest(
        patient_id="PAT_EMERG_999",
        history_type=HistoryType.ALLOPATHIC,
        language="en"
    )
    r1 = await DialogueController.start_session(req)

    # Patient reports crushing chest pain with left arm radiation
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="Suddenly I am having crushing chest pain radiating to left arm and sweating"
        )
    )
    assert r2.red_flag_alert is not None
    assert r2.red_flag_alert.is_red_flag is True
    assert r2.red_flag_alert.severity == RedFlagSeverity.CRITICAL
    assert r2.phase == InterviewPhase.RED_FLAG_TRIAGE
    assert r2.is_completed is True
    assert "EMERGENCY" in r2.question_text

# -------------------------------------------------------------
# 5. FastAPI Endpoints & Document Context Integration Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_document_context_integration():
    """Verify OCR extracted document context is injected and verified."""
    req = DialogueStartRequest(
        patient_id="PAT_DOC_003",
        history_type=HistoryType.ALLOPATHIC,
        extracted_document_context={
            "medications": [{"name": "Metformin 500mg", "dosage": "1-0-1"}],
            "diagnosis": [{"condition": "Type 2 Diabetes Mellitus"}]
        }
    )
    r1 = await DialogueController.start_session(req)
    session = get_session(r1.session_id)
    assert session is not None
    assert "Metformin 500mg" in str(session.extracted_document_context)

@pytest.mark.asyncio
async def test_fastapi_endpoints_workflow():
    """Test full FastAPI REST endpoints workflow via httpx AsyncClient."""
    from app.main import app
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. CCRAS Battery
        res_bat = await client.get("/api/v1/dialogue/ccras-pas/battery")
        assert res_bat.status_code == 200
        assert "domains" in res_bat.json()

        # 2. Standalone Red Flag Check
        res_rf = await client.post(
            "/api/v1/dialogue/red-flag-check",
            json={"text": "I am having sudden facial droop and cannot speak"}
        )
        assert res_rf.status_code == 200
        assert res_rf.json()["is_red_flag"] is True

        # 3. Start Session
        res_start = await client.post(
            "/api/v1/dialogue/start",
            json={
                "patient_id": "PAT_REST_100",
                "history_type": "allopathic",
                "language": "en"
            }
        )
        assert res_start.status_code == 201
        data_start = res_start.json()
        sess_id = data_start["session_id"]

        # 4. Turn 1
        res_turn1 = await client.post(
            "/api/v1/dialogue/turn",
            json={
                "session_id": sess_id,
                "patient_response": "I have persistent stomach pain after meals"
            }
        )
        assert res_turn1.status_code == 200
        assert res_turn1.json()["turn_number"] > 1

        # 5. Get Session
        res_get = await client.get(f"/api/v1/dialogue/session/{sess_id}")
        assert res_get.status_code == 200
        assert res_get.json()["patient_id"] == "PAT_REST_100"

        # 6. NAMASTE Diagnostic Code Search & Lookup
        res_nam = await client.get("/api/v1/dialogue/namaste-lookup?query=Sandhivata")
        assert res_nam.status_code == 200
        items = res_nam.json()
        assert len(items) > 0
        assert items[0]["namaste_code"] == "AAE-16"
        assert "TM2-SD01.1" in items[0]["icd11_tm2_code"]

        res_code = await client.get("/api/v1/dialogue/namaste-lookup/AAE-16")
        assert res_code.status_code == 200
        assert "Sandhivata" in res_code.json()["ayurvedic_name"]

@pytest.mark.asyncio
async def test_fhir_r4_bundle_export():
    """Verify FHIR R4 Bundle conversion contains Patient, Encounter, Condition, and QuestionnaireResponse."""
    from app.ai.dialogue import convert_dialogue_to_fhir_r4
    req = DialogueStartRequest(
        patient_id="ABHA_PAT_987654",
        history_type=HistoryType.AYURVEDIC,
        language="en"
    )
    r1 = await DialogueController.start_session(req)
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have severe joint pain and knee swelling (Sandhivata)"
        )
    )
    session = get_session(r1.session_id)
    bundle = convert_dialogue_to_fhir_r4(session)
    
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
    assert "Patient" in resource_types
    assert "Encounter" in resource_types
    assert "Condition" in resource_types
    assert "QuestionnaireResponse" in resource_types

# -------------------------------------------------------------
# 6. Dashavidha Questionnaires, Real NAMASTE & Urgency Escalation
# -------------------------------------------------------------

def test_dashavidha_static_questionnaires():
    """Verify Satmya, Sattva, and Vyayama Shakti scoring from classical criteria."""
    from app.ai.dialogue import (
        score_satmya_assessment,
        score_sattva_assessment,
        score_vyayama_assessment,
        classify_vaya_lifestage,
        EXCLUDED_PHYSICAL_EXAM_PARAMETERS
    )

    # 1. Satmya (Pravara)
    satmya_ans = [{"score": 3}, {"score": 3}, {"score": 3}]
    res_sat = score_satmya_assessment(satmya_ans)
    assert res_sat["score_percentage"] == 100.0
    assert "Pravara" in res_sat["classification"]

    # 2. Sattva (Pravara vs Avara)
    sattva_high = [{"score": 3}, {"score": 3}, {"score": 3}]
    assert "Pravara" in score_sattva_assessment(sattva_high)["classification"]

    sattva_low = [{"score": 1}, {"score": 1}, {"score": 1}]
    assert "Avara" in score_sattva_assessment(sattva_low)["classification"]

    # 3. Vyayama Shakti
    vy_ans = [{"score": 2}, {"score": 2}]
    assert "Madhyama" in score_vyayama_assessment(vy_ans)["classification"]

    # 4. Vaya
    assert "Vriddha" in classify_vaya_lifestage(68)
    assert "Madhyama" in classify_vaya_lifestage(35)
    assert "Bala" in classify_vaya_lifestage(12)

    # 5. Scoping distinction
    excluded_names = [p["parameter"] for p in EXCLUDED_PHYSICAL_EXAM_PARAMETERS]
    assert "Sara" in excluded_names
    assert "Samhanana" in excluded_names
    assert "Pramana" in excluded_names

def test_real_namaste_official_alphanumeric_codes():
    """Verify real official NAMASTE portal alphanumeric codes (AAE-16, EB-4, EC-6, EA-4, ED-5)."""
    from app.ai.dialogue import search_namaste_codes, get_namaste_item_by_code

    # Sandhigatavata (AAE-16)
    sandhi = get_namaste_item_by_code("AAE-16")
    assert sandhi is not None
    assert "Sandhigatavata" in sandhi.ayurvedic_name
    assert sandhi.icd11_tm2_code == "TM2-SD01.1"

    # Amlapitta (EB-4)
    amla = get_namaste_item_by_code("EB-4")
    assert amla is not None
    assert "Amlapitta" in amla.ayurvedic_name

    # Amavata (EC-6)
    ama = get_namaste_item_by_code("EC-6")
    assert ama is not None
    assert "Amavata" in ama.ayurvedic_name

    # Search keyword
    res = search_namaste_codes("Sciatica")
    assert len(res) > 0
    assert res[0].namaste_code == "AAB-37"

@pytest.mark.asyncio
async def test_prior_history_chunk_urgency_escalation():
    """Verify chest pain in a patient with a documented prior MI chunk triggers elevated urgency."""
    req = DialogueStartRequest(
        patient_id="PAT_PRIOR_MI_99",
        history_type=HistoryType.ALLOPATHIC,
        patient_history_chunks=["Documented Prior History: Acute Anterior Wall Myocardial Infarction in 2024, Stent placed."]
    )
    r1 = await DialogueController.start_session(req)
    
    # Patient reports mild chest tightness/pressure
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I am feeling mild chest pressure and heaviness since afternoon"
        )
    )
    
    assert r2.red_flag_alert is not None
    assert r2.red_flag_alert.is_red_flag is True
    assert r2.red_flag_alert.severity == RedFlagSeverity.CRITICAL
    assert "Prior MI" in r2.red_flag_alert.category or "ELEVATED URGENCY" in r2.red_flag_alert.emergency_message

@pytest.mark.asyncio
async def test_new_patient_empty_history_chunks():
    """Verify new patient with empty patient_history_chunks works gracefully without errors."""
    req = DialogueStartRequest(
        patient_id="PAT_NEW_001",
        history_type=HistoryType.ALLOPATHIC,
        patient_history_chunks=[]  # Empty history
    )
    r1 = await DialogueController.start_session(req)
    assert r1.session_id is not None
    assert r1.turn_number == 1
    
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have mild back stiffness in the morning"
        )
    )
    assert r2.turn_number == 3
    assert r2.red_flag_alert is None

@pytest.mark.asyncio
async def test_mixed_integrative_care_mode():
    """Verify HistoryType.MIXED operates Allopathic HPI + Ayurvedic evaluation."""
    req = DialogueStartRequest(
        patient_id="PAT_MIXED_777",
        history_type=HistoryType.MIXED,
        age=45
    )
    r1 = await DialogueController.start_session(req)
    assert r1.phase == InterviewPhase.CHIEF_COMPLAINT
    
    # Turn 1: Chief complaint
    r2 = await DialogueController.process_turn(
        DialogueTurnInput(
            session_id=r1.session_id,
            patient_response="I have chronic burning in stomach and tingling in feet"
        )
    )
    session = get_session(r1.session_id)
    assert session.clinical_history.standard_history.chief_complaint is not None
    assert session.clinical_history.ayurvedic_assessment.vaya_lifestage is not None

