import asyncio
import json
from app.schemas.dialogue import (
    HistoryType,
    DialogueStartRequest,
    DialogueTurnInput
)
from app.ai.dialogue.controller import DialogueController
from app.ai.dialogue.fhir_adapter import convert_dialogue_to_fhir_r4
from app.ai.dialogue.session_store import get_session

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

async def run_interactive_session(history_type: HistoryType):
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}MediKiosk Clinical Dialogue Assistant ({history_type.value.upper()} MODE){RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")

    patient_id = "PAT_SIM_" + ("ALLO" if history_type == HistoryType.ALLOPATHIC else "AYUR")
    req = DialogueStartRequest(
        patient_id=patient_id,
        history_type=history_type,
        language="en"
    )

    # Start Session
    res = await DialogueController.start_session(req)
    session_id = res.session_id

    while not res.is_completed:
        print(f"{BOLD}{YELLOW}Turn {res.turn_number} / {res.max_turns} [{res.phase.value}]{RESET}")
        print(f"{GREEN}AI Assistant:{RESET} {res.question_text}\n")

        # Display Quick Touch Options if present
        if res.touch_options:
            print(f"{CYAN}Available Touch Options:{RESET}")
            for idx, opt in enumerate(res.touch_options, 1):
                print(f"  [{idx}] {opt.label}")
            print(f"  [Or type your own custom response below]\n")

        user_input = input(f"{BOLD}Patient response > {RESET}").strip()
        if not user_input:
            user_input = "No symptoms to report"

        # Check if user picked a numbered option
        selected_opt_id = None
        if user_input.isdigit():
            opt_idx = int(user_input) - 1
            if 0 <= opt_idx < len(res.touch_options):
                selected_opt = res.touch_options[opt_idx]
                user_input = selected_opt.value
                selected_opt_id = selected_opt.id
                print(f"{CYAN}[Selected Touch Chip]: {selected_opt.label}{RESET}\n")

        # Submit Turn
        res = await DialogueController.process_turn(
            DialogueTurnInput(
                session_id=session_id,
                patient_response=user_input,
                selected_option_id=selected_opt_id
            )
        )

        # Check Red Flag
        if res.red_flag_alert and res.red_flag_alert.is_red_flag:
            print(f"\n{RED}{BOLD}🚨 RED-FLAG EMERGENCY TRIGGERED! 🚨{RESET}")
            print(f"{RED}Category:{RESET} {res.red_flag_alert.category}")
            print(f"{RED}Alert Message:{RESET} {res.red_flag_alert.emergency_message}")
            print(f"{RED}Triage Destination:{RESET} {res.red_flag_alert.triage_destination}")
            break

    print(f"\n{BOLD}{GREEN}======================================================{RESET}")
    print(f"{BOLD}{GREEN}✅ INTAKE INTERVIEW COMPLETED{RESET}")
    print(f"{BOLD}{GREEN}======================================================{RESET}")
    
    # Print Final Summary
    session = get_session(session_id)
    if session:
        hist = session.clinical_history
        print(f"\n{BOLD}Structured Clinical History Summary:{RESET}")
        print(f"  • Chief Complaint: {hist.standard_history.chief_complaint}")
        print(f"  • HPI: {hist.standard_history.hpi}")
        
        if history_type == HistoryType.ALLOPATHIC:
            soc = hist.standard_history.socrates
            print(f"  • SOCRATES Site: {soc.site}")
            print(f"  • SOCRATES Character: {soc.character}")
            print(f"  • SOCRATES Severity: {soc.severity_score}/10")
            print(f"  • SOCRATES Radiation: {soc.radiation}")
            print(f"  • Timing / Course: {soc.time_course}")
            print(f"  • Exacerbating / Relieving: {soc.exacerbating_relieving}")
        else:
            ayur = hist.ayurvedic_assessment
            if ayur:
                print(f"  • Vikriti (Imbalance): {ayur.vikriti}")
                print(f"  • Agni (Digestive Fire): {ayur.agni}")
                print(f"  • Koshtha (Bowel Type): {ayur.koshtha}")
                print(f"  • Ahara-Vihara (Lifestyle): {ayur.ahara_vihara}")
                if ayur.prakriti:
                    p = ayur.prakriti
                    print(f"  • Dominant Prakriti: {p.dominant_prakriti} ({p.phenotype_type})")
                    print(f"    - Vata: {p.vata_percentage}% | Pitta: {p.pitta_percentage}% | Kapha: {p.kapha_percentage}%")

        # FHIR R4 Bundle
        fhir_bundle = convert_dialogue_to_fhir_r4(session)
        print(f"\n{CYAN}FHIR R4 Bundle Resource Count:{RESET} {len(fhir_bundle.get('entry', []))} resources")
        print(f"{CYAN}FHIR Document Bundle ID:{RESET} {fhir_bundle.get('id')}\n")

def main():
    print(f"\n{BOLD}{CYAN}MediKiosk — Clinical Dialogue Engine CLI Simulator{RESET}")
    print("1. Allopathic SOCRATES Interview Simulation")
    print("2. Ayurvedic CCRAS-PAS & Dashavidha Pariksha Interview Simulation")
    print("3. Emergency Red-Flag Instant Trigger Test")
    print("4. Exit")
    
    choice = input("\nSelect an option [1-4]: ").strip()
    if choice == "1":
        asyncio.run(run_interactive_session(HistoryType.ALLOPATHIC))
    elif choice == "2":
        asyncio.run(run_interactive_session(HistoryType.AYURVEDIC))
    elif choice == "3":
        async def run_emergency():
            req = DialogueStartRequest(
                patient_id="PAT_EMERG_911",
                history_type=HistoryType.ALLOPATHIC,
                chief_complaint_hint="I have acute crushing chest pain radiating to my left arm with cold sweats"
            )
            res = await DialogueController.start_session(req)
            print(f"\n{RED}{BOLD}🚨 RED-FLAG EMERGENCY TRIGGERED ON INTAKE!{RESET}")
            print(f"{RED}Question / Alert:{RESET} {res.question_text}")
            print(f"{RED}Destination:{RESET} {res.red_flag_alert.triage_destination}\n")
        asyncio.run(run_emergency())
    else:
        print("Exiting simulator.")

if __name__ == "__main__":
    main()
