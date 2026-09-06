# backend/app/ai/dialogue/protocols/base.py
"""
MediKiosk — Base Clinical Dialogue Protocol Strategy (ABC)
Defines the universal contract for all clinical paradigms (Allopathy, Ayurveda, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.ai.dialogue.models import PatientContext, DialogueTurnResult

class ClinicalProtocol(ABC):
    """
    Abstract Strategy defining domain-specific prompt engineering,
    slot-tracking dimensions, and gold-standard clinical documentation formatting.
    """
    system_name: str
    target_slots: List[str]

    @abstractmethod
    def build_system_prompt(
        self,
        patient_context: PatientContext,
        rag_context_snippets: List[str]
    ) -> str:
        """Constructs the LLM system instructions tailored to this medical paradigm."""
        pass

    @abstractmethod
    def normalize_state(
        self,
        raw_state: Optional[Dict[str, Any]],
        accumulated_text: str = ""
    ) -> Dict[str, Any]:
        """Validates and calculates covered vs missing slots for this paradigm."""
        pass

    @abstractmethod
    def format_doctor_summary(
        self,
        final_state: Dict[str, Any],
        patient_context: PatientContext
    ) -> str:
        """Formats the final gold-standard clinical intake summary for the attending physician/vaidya."""
        pass
