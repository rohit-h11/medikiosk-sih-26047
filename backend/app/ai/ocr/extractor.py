"""
Hybrid Document Extraction Engine for MediKiosk (Problem Statement 26047).
Orchestrates Dual-Stream Preprocessing, Handwritten/Printed Classification,
Quality Routing, Multimodal Vision LLM Extraction, and RAG Embedding Generation.
"""

from typing import Union, Optional, Dict, Any, List
import numpy as np

from .config import PreprocessConfig, VisionLLMConfig, DocumentType, RoutingDecision
from .pipeline import run_pipeline, PipelineResult
from .schemas import ExtractedDocumentData
from .vision_llm import VisionLLMClient
from .fast_ocr import FastOCREngine



class DocumentExtractor:
    """End-to-end clinical document digitization and structured extraction engine."""

    def __init__(
        self,
        preprocess_cfg: Optional[PreprocessConfig] = None,
        vision_cfg: Optional[VisionLLMConfig] = None
    ):
        self.preprocess_cfg = preprocess_cfg or PreprocessConfig()
        self.vision_cfg = vision_cfg or VisionLLMConfig()
        self.vision_client = VisionLLMClient(self.vision_cfg)
        self.fast_ocr_client = FastOCREngine()

    def process_and_extract(
        self,
        image_input: Union[str, bytes, np.ndarray],
        patient_id: Optional[str] = None,
        debug_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs complete pipeline on an input document image:
         1. Dual-stream Preprocessing (RGB + Binary)
         2. Handwriting vs. Printed Classification
         3. Text-ROI Quality Assessment & Routing
         4. Clinical Extraction via Vision LLM / Fast OCR
         5. RAG Embedding Chunk Preparation
        """
        pipeline_result: PipelineResult = run_pipeline(
            image_input=image_input,
            cfg=self.preprocess_cfg,
            debug_dir=debug_dir
        )

        quality = pipeline_result.quality
        route = pipeline_result.route
        doc_type = pipeline_result.doc_type

        if route == RoutingDecision.RETAKE:
            return {
                "success": False,
                "routing_decision": route.value,
                "document_type": doc_type.value,
                "quality_score": quality.legibility_score,
                "is_acceptable": False,
                "reasons": quality.reasons,
                "retake_required": True,
                "message": "Document image quality is insufficient for accurate clinical extraction. Please ask patient to retake.",
                "extracted_data": None,
                "rag_chunks": []
            }

        # ── DUAL ENGINE ROUTING ──────────────────────────────────────────────────
        # OCR_FAST        → PRINTED / LAB_REPORT  → FastOCREngine  (100% local, zero API cost)
        # VISION_LLM      → HANDWRITTEN           → Gemini Vision API
        # HYBRID_FUSION   → HYBRID_MIXED          → Gemini Vision API (handles both streams)
        # VISION_LLM_FALLBACK → borderline quality → Gemini Vision API (resilient)
        # ─────────────────────────────────────────────────────────────────────────

        if route == RoutingDecision.OCR_FAST:
            # PRINTED or LAB_REPORT: 100% local Tesseract OCR — no Gemini API call, zero cost
            extracted_data: ExtractedDocumentData = self.fast_ocr_client.extract_from_image(
                image_bin=pipeline_result.final_image_binary,
                image_rgb=pipeline_result.final_image_rgb,
                doc_type=doc_type,
                ocr_hint_text=f"Detected Document Type: {doc_type.value}, Text Regions Count: {len(pipeline_result.text_regions)}"
            )
        elif route in (
            RoutingDecision.VISION_LLM,
            RoutingDecision.HYBRID_FUSION,
            RoutingDecision.VISION_LLM_FALLBACK,
        ):
            # HANDWRITTEN / HYBRID_MIXED / low-quality fallback: Gemini multimodal Vision LLM
            extracted_data: ExtractedDocumentData = self.vision_client.extract_from_image(
                image_rgb=pipeline_result.final_image_rgb,
                doc_type=doc_type,
                ocr_hint_text=f"Detected Document Type: {doc_type.value}, Text Regions Count: {len(pipeline_result.text_regions)}"
            )
        else:
            # Safety net — should never reach here after RETAKE is handled above
            extracted_data: ExtractedDocumentData = self.vision_client.extract_from_image(
                image_rgb=pipeline_result.final_image_rgb,
                doc_type=doc_type
            )

        rag_chunks = self._generate_rag_chunks(extracted_data, patient_id=patient_id)

        return {
            "success": True,
            "routing_decision": route.value,
            "document_type": doc_type.value,
            "quality_score": quality.legibility_score,
            "is_acceptable": quality.is_acceptable,
            "reasons": quality.reasons,
            "retake_required": False,
            "extracted_data": extracted_data.model_dump(),
            "rag_chunks": rag_chunks
        }

    def _generate_rag_chunks(
        self,
        data: ExtractedDocumentData,
        patient_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates semantic medical chunks for vector embedding and retrieval (Module B -> Module C/RAG).
        """
        chunks = []
        doc_date = data.document_date or "Unknown Date"
        hospital = data.clinic_or_hospital or "OPD Clinic"
        sys_type = data.medicine_system.value

        # Chunk 1: Document Overview & Diagnoses
        diag_lines = [f"- {d.condition} (Code: {d.code or 'N/A'}, System: {d.system_terminology})" for d in data.diagnoses]
        diag_text = "\n".join(diag_lines) if diag_lines else "No specific diagnosis listed."
        
        overview_content = (
            f"Document Date: {doc_date}\n"
            f"Facility: {hospital}\n"
            f"Medicine System: {sys_type.capitalize()}\n"
            f"Diagnoses:\n{diag_text}\n"
            f"Chief Complaints: {', '.join(data.chief_complaints) if data.chief_complaints else 'None recorded'}"
        )
        chunks.append({
            "chunk_index": 0,
            "chunk_type": "clinical_summary",
            "content": overview_content,
            "metadata": {
                "patient_id": patient_id,
                "date": doc_date,
                "system": sys_type
            }
        })

        # Chunk 2: Medications & Ayurvedic Formulations
        if data.medications:
            med_lines = []
            for m in data.medications:
                line = f"- {m.name} | Dose: {m.dosage or 'N/A'} | Freq: {m.frequency or 'N/A'} | Duration: {m.duration or 'N/A'}"
                if m.is_ayurvedic and m.ayurvedic_form:
                    line += f" | Form: {m.ayurvedic_form.value} | Anupana: {m.anupana or 'Water'} | Kala: {m.kala.value if m.kala else 'N/A'}"
                if m.instructions:
                    line += f" | Instructions: {m.instructions}"
                med_lines.append(line)
                
            med_content = f"Prescribed Medications ({doc_date} at {hospital}):\n" + "\n".join(med_lines)
            chunks.append({
                "chunk_index": 1,
                "chunk_type": "medications",
                "content": med_content,
                "metadata": {
                    "patient_id": patient_id,
                    "date": doc_date,
                    "system": sys_type
                }
            })

        # Chunk 3: Lab Investigations & Findings
        if data.lab_investigations:
            lab_lines = []
            for lab in data.lab_investigations:
                flag_str = f" [{lab.abnormal_flag.value.upper()}]" if (lab.abnormal_flag and lab.abnormal_flag.value != "normal") else ""
                lab_lines.append(f"- {lab.test_name}: {lab.observed_value} {lab.unit or ''} (Ref: {lab.reference_range or 'N/A'}){flag_str}")
                
            lab_content = f"Lab Investigation Results ({doc_date}):\n" + "\n".join(lab_lines)
            chunks.append({
                "chunk_index": 2,
                "chunk_type": "lab_reports",
                "content": lab_content,
                "metadata": {
                    "patient_id": patient_id,
                    "date": doc_date
                }
            })

        # Chunk 4: Ayurvedic Specific Assessment (Prakriti, Agni, Dosha)
        if data.ayurvedic_assessment:
            ayur = data.ayurvedic_assessment
            ayur_content = (
                f"Ayurvedic Clinical Assessment ({doc_date}):\n"
                f"Prakriti: {ayur.prakriti or 'N/A'}\n"
                f"Vikriti (Imbalance): {ayur.vikriti or 'N/A'}\n"
                f"Agni (Digestive Fire): {ayur.agni or 'N/A'}\n"
                f"Koshtha: {ayur.koshtha or 'N/A'}\n"
                f"Diet & Lifestyle (Pathya-Apathya): {', '.join(data.diet_and_lifestyle_advice) if data.diet_and_lifestyle_advice else 'N/A'}"
            )
            chunks.append({
                "chunk_index": 3,
                "chunk_type": "ayurvedic_assessment",
                "content": ayur_content,
                "metadata": {
                    "patient_id": patient_id,
                    "date": doc_date,
                    "system": "ayurvedic"
                }
            })

        return chunks


def extract_document_data(
    image_input: Union[str, bytes, np.ndarray],
    preprocess_cfg: Optional[PreprocessConfig] = None,
    vision_cfg: Optional[VisionLLMConfig] = None,
    patient_id: Optional[str] = None,
    debug_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Convenience helper to run complete extraction pipeline."""
    extractor = DocumentExtractor(preprocess_cfg=preprocess_cfg, vision_cfg=vision_cfg)
    return extractor.process_and_extract(image_input, patient_id=patient_id, debug_dir=debug_dir)
