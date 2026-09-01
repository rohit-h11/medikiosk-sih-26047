"""
Fast Local OCR Engine for MediKiosk (Problem Statement 26047).
Handles PRINTED and LAB_REPORT document types using pytesseract (Tesseract OCR).
Zero API cost — runs 100% locally. Only called when routing decision is OCR_FAST.
Handwritten / hybrid documents are always routed to VisionLLMClient (Gemini).
"""

import re
from typing import Optional, List, Dict, Any
import numpy as np

from .config import DocumentType, MedicineSystem
from .schemas import (
    ExtractedDocumentData,
    MedicationItem,
    DiagnosisItem,
    LabInvestigationItem,
    AbnormalFlag,
    AyurvedicForm,
    AyurvedicKala,
)


# ---------------------------------------------------------------------------
# Regex helpers for structured field extraction from raw OCR text
# ---------------------------------------------------------------------------

_RE_PATIENT_NAME = re.compile(
    r"(?:patient\s*name|name|pt\.?\s*name)[:\s]+([A-Za-z][A-Za-z\s\.]{2,40})",
    re.IGNORECASE
)
_RE_AGE = re.compile(
    r"\b(?:age|yr|years?)[:\s/]*(\d{1,3})\s*(?:yrs?|years?|Y|M|D)?\b",
    re.IGNORECASE
)
_RE_GENDER = re.compile(
    r"\b(male|female|m|f|M/F|F/M)\b",
    re.IGNORECASE
)
_RE_DOCTOR = re.compile(
    r"(?:dr\.?|doctor|physician|consultant)[:\s]+([A-Za-z][A-Za-z\s\.]{2,50})",
    re.IGNORECASE
)
_RE_HOSPITAL = re.compile(
    r"(?:hospital|clinic|centre|center|institute|nursing\s*home)[:\s]*([A-Za-z][A-Za-z\s\.,&\-]{3,60})",
    re.IGNORECASE
)
_RE_DATE = re.compile(
    r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})\b"
)
_RE_BP = re.compile(r"\b(\d{2,3}\s*/\s*\d{2,3})\s*(?:mmhg|mm\s*hg)?\b", re.IGNORECASE)
_RE_PULSE = re.compile(r"\b(?:pulse|pr|hr)[:\s]*(\d{2,3})\s*(?:bpm|/min)?\b", re.IGNORECASE)
_RE_WEIGHT = re.compile(r"\b(?:weight|wt)[:\s]*(\d{2,3}(?:\.\d)?)\s*(?:kg|kgs)?\b", re.IGNORECASE)
_RE_TEMP = re.compile(r"\b(?:temp|temperature)[:\s]*(\d{2,3}(?:\.\d)?)\s*(?:°?[CF]|f|c)?\b", re.IGNORECASE)
_RE_SPO2 = re.compile(r"\b(?:spo2|spo₂|o2\s*sat)[:\s]*(\d{2,3})\s*%?\b", re.IGNORECASE)

# Lab value lines: e.g. "Haemoglobin    12.5    g/dL    13.0-17.0"
_RE_LAB_LINE = re.compile(
    r"([A-Za-z][A-Za-z0-9\s\(\)\/\-\.]{2,40})\s+"
    r"([<>]?\d+\.?\d*)\s+"
    r"([a-zA-Z\/%µμ]+(?:/[a-zA-Z]+)?)\s*"
    r"([\d\.]+\s*[-–]\s*[\d\.]+)?",
    re.IGNORECASE
)

# Medication lines: e.g. "Tab. Metformin 500mg BD x 30 days"
_RE_MED_LINE = re.compile(
    r"(?:tab(?:let)?s?\.?|cap(?:sule)?s?\.?|syr(?:up)?\.?|inj\.?|drop?s?\.?|cream|oint(?:ment)?\.?)\s+"
    r"([A-Za-z][A-Za-z0-9\s\+\-\.\/]{2,50})",
    re.IGNORECASE
)
_RE_DOSAGE = re.compile(r"\b(\d+\.?\d*)\s*(mg|mcg|ml|g|iu|units?)\b", re.IGNORECASE)
_RE_FREQ = re.compile(
    r"\b(OD|BD|BID|TDS|TID|QID|SOS|PRN|HS|AC|PC|STAT|once\s*daily|twice\s*daily|thrice\s*daily)\b",
    re.IGNORECASE
)
_RE_DURATION = re.compile(r"\b(?:for|x|×)?\s*(\d+)\s*(day|days|week|weeks|month|months)\b", re.IGNORECASE)


class FastOCREngine:
    """
    Local OCR extraction engine for PRINTED and LAB_REPORT documents.
    Uses pytesseract (Tesseract) for text extraction + regex heuristics
    for structured field parsing. Zero API cost, works fully offline.
    """

    def __init__(self):
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract  # type: ignore
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def _run_ocr(self, image_rgb: np.ndarray) -> str:
        """Runs Tesseract OCR on the RGB image and returns raw text."""
        if not self._tesseract_available:
            return ""
        try:
            import pytesseract  # type: ignore
            import cv2
            # Use PSM 6 (uniform block of text) — good for printed prescriptions
            config = r"--oem 3 --psm 6 -l eng+hin"
            gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY) if len(image_rgb.shape) == 3 else image_rgb
            text = pytesseract.image_to_string(gray, config=config)
            return text.strip()
        except Exception as e:
            print(f"[FastOCR] Tesseract OCR failed: {e}")
            return ""

    def extract_from_image(
        self,
        image_bin: np.ndarray,
        image_rgb: np.ndarray,
        doc_type: DocumentType = DocumentType.PRINTED,
        ocr_hint_text: Optional[str] = None,
    ) -> ExtractedDocumentData:
        """
        Main entry point. Runs local OCR and regex-based structured extraction.
        Falls back to a minimal schema if Tesseract is not installed.
        """
        raw_text = self._run_ocr(image_rgb)

        if not raw_text and ocr_hint_text:
            raw_text = ocr_hint_text

        if doc_type == DocumentType.LAB_REPORT:
            return self._extract_lab_report(raw_text, doc_type)
        else:
            return self._extract_prescription(raw_text, doc_type)

    # ------------------------------------------------------------------
    # PRESCRIPTION (PRINTED) EXTRACTION
    # ------------------------------------------------------------------
    def _extract_prescription(self, raw_text: str, doc_type: DocumentType) -> ExtractedDocumentData:
        lines = raw_text.splitlines()

        patient_name = self._first_match(_RE_PATIENT_NAME, raw_text)
        age = self._first_match(_RE_AGE, raw_text)
        gender_raw = self._first_match(_RE_GENDER, raw_text)
        gender = self._normalize_gender(gender_raw)
        doctor = self._first_match(_RE_DOCTOR, raw_text)
        hospital = self._first_match(_RE_HOSPITAL, raw_text)
        date = self._first_match(_RE_DATE, raw_text)

        vitals: Dict[str, Any] = {}
        bp = self._first_match(_RE_BP, raw_text)
        if bp:
            vitals["bp"] = bp + " mmHg"
        pulse = self._first_match(_RE_PULSE, raw_text)
        if pulse:
            vitals["pulse"] = pulse + " bpm"
        weight = self._first_match(_RE_WEIGHT, raw_text)
        if weight:
            vitals["weight"] = weight + " kg"
        temp = self._first_match(_RE_TEMP, raw_text)
        if temp:
            vitals["temp"] = temp + "°F"
        spo2 = self._first_match(_RE_SPO2, raw_text)
        if spo2:
            vitals["spo2"] = spo2 + "%"

        medications = self._extract_medications(lines)
        complaints = self._extract_complaints(raw_text)

        confidence = 0.82 if self._tesseract_available else 0.30

        return ExtractedDocumentData(
            document_type=doc_type,
            medicine_system=MedicineSystem.ALLOPATHIC,
            patient_name=patient_name,
            patient_age=age,
            patient_gender=gender,
            doctor_name=doctor,
            clinic_or_hospital=hospital,
            document_date=date,
            chief_complaints=complaints,
            vitals=vitals if vitals else {},
            medications=medications,
            diagnoses=[],
            lab_investigations=[],
            raw_text=raw_text[:2000],
            handwritten_ratio=0.0,
            extraction_confidence=confidence,
        )

    # ------------------------------------------------------------------
    # LAB REPORT EXTRACTION
    # ------------------------------------------------------------------
    def _extract_lab_report(self, raw_text: str, doc_type: DocumentType) -> ExtractedDocumentData:
        patient_name = self._first_match(_RE_PATIENT_NAME, raw_text)
        age = self._first_match(_RE_AGE, raw_text)
        gender_raw = self._first_match(_RE_GENDER, raw_text)
        gender = self._normalize_gender(gender_raw)
        hospital = self._first_match(_RE_HOSPITAL, raw_text)
        date = self._first_match(_RE_DATE, raw_text)

        lab_items = self._extract_lab_values(raw_text)

        confidence = 0.88 if self._tesseract_available else 0.30

        return ExtractedDocumentData(
            document_type=doc_type,
            medicine_system=MedicineSystem.ALLOPATHIC,
            patient_name=patient_name,
            patient_age=age,
            patient_gender=gender,
            clinic_or_hospital=hospital,
            document_date=date,
            lab_investigations=lab_items,
            raw_text=raw_text[:2000],
            handwritten_ratio=0.0,
            extraction_confidence=confidence,
        )

    # ------------------------------------------------------------------
    # FIELD PARSERS
    # ------------------------------------------------------------------
    def _first_match(self, pattern: re.Pattern, text: str) -> Optional[str]:
        m = pattern.search(text)
        return m.group(1).strip() if m else None

    def _normalize_gender(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        r = raw.strip().lower()
        if r in ("m", "male"):
            return "Male"
        if r in ("f", "female"):
            return "Female"
        return raw.capitalize()

    def _extract_medications(self, lines: List[str]) -> List[MedicationItem]:
        meds = []
        for line in lines:
            m = _RE_MED_LINE.search(line)
            if not m:
                continue
            name = m.group(1).strip()
            if len(name) < 3:
                continue

            dosage_m = _RE_DOSAGE.search(line)
            dosage = f"{dosage_m.group(1)} {dosage_m.group(2)}" if dosage_m else None

            freq_m = _RE_FREQ.search(line)
            frequency = freq_m.group(1).upper() if freq_m else None

            dur_m = _RE_DURATION.search(line)
            duration = f"{dur_m.group(1)} {dur_m.group(2)}" if dur_m else None

            meds.append(MedicationItem(
                name=name,
                dosage=dosage,
                frequency=frequency,
                duration=duration,
                route="oral",
                is_ayurvedic=False,
                confidence=0.80,
            ))
        return meds

    def _extract_lab_values(self, raw_text: str) -> List[LabInvestigationItem]:
        items = []
        for m in _RE_LAB_LINE.finditer(raw_text):
            test_name = m.group(1).strip()
            value = m.group(2).strip()
            unit = m.group(3).strip() if m.group(3) else None
            ref_range = m.group(4).strip() if m.group(4) else None

            if len(test_name) < 3 or not value:
                continue

            flag = self._compute_flag(value, ref_range)

            items.append(LabInvestigationItem(
                test_name=test_name,
                observed_value=value,
                unit=unit,
                reference_range=ref_range,
                abnormal_flag=flag,
            ))
        return items[:30]  # cap at 30 to avoid noise

    def _compute_flag(self, value_str: str, ref_range: Optional[str]) -> AbnormalFlag:
        """Simple numeric range check to compute abnormal_flag."""
        if not ref_range:
            return AbnormalFlag.NORMAL
        try:
            val = float(re.sub(r"[<>]", "", value_str))
            parts = re.split(r"[-–]", ref_range)
            if len(parts) == 2:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                if val < low * 0.8:
                    return AbnormalFlag.CRITICAL_LOW
                if val < low:
                    return AbnormalFlag.LOW
                if val > high * 1.5:
                    return AbnormalFlag.CRITICAL_HIGH
                if val > high:
                    return AbnormalFlag.HIGH
        except (ValueError, IndexError):
            pass
        return AbnormalFlag.NORMAL

    def _extract_complaints(self, raw_text: str) -> List[str]:
        """Extracts chief complaints / presenting symptoms from printed Rx."""
        complaints = []
        for m in re.finditer(
            r"(?:c/o|complaints?|presenting\s*complaints?|chief\s*complaints?)[:\s]+(.+?)(?:\n|$)",
            raw_text,
            re.IGNORECASE
        ):
            line = m.group(1).strip()
            if line:
                complaints.extend([c.strip() for c in re.split(r"[,;]", line) if c.strip()])
        return complaints[:10]
