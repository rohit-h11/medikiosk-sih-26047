from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentType(str, Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    AYURVEDIC_RECORD = "ayurvedic_record"
    OTHER = "other"


class OCRStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUALITY_REJECTED = "quality_rejected"


class PreIngestionCheckResult(BaseModel):
    """
    Result of the fast CPU-based quality, blur, and duplicate triage gate.
    """
    is_acceptable: bool = Field(..., description="True if image passes sharpness, contrast, and glare checks")
    is_duplicate: bool = Field(False, description="True if an identical or near-identical image already exists")
    duplicate_reason: Optional[str] = Field(None, description="'EXACT_SHA256' or 'VISUAL_DHASH' or None")
    existing_document_id: Optional[str] = Field(None, description="UUID of existing document if duplicate detected")
    
    # Forensic & Quality Metrics
    sha256_hash: str = Field(..., description="Cryptographic SHA-256 checksum of raw image bytes")
    dhash_fingerprint: Optional[str] = Field(None, description="64-bit perceptual structural difference hash")
    sharpness: float = Field(0.0, description="Laplacian variance (higher = sharper)")
    contrast_std: float = Field(0.0, description="Standard deviation of grayscale luminance")
    glare_ratio: float = Field(0.0, description="Ratio of specular highlight / overexposed pixels")
    quality_score: float = Field(100.0, description="Composite 0-100 quality score")
    
    reasons: List[str] = Field(default_factory=list, description="Explanatory reasons if rejected or flagged")
    suggested_action: str = Field("PROCEED", description="'PROCEED', 'RETAKE_CAMERA', 'LINK_EXISTING', 'REJECT'")


class DocumentUploadMetadata(BaseModel):
    """Metadata passed alongside raw document uploads."""
    patient_id: str = Field(..., description="Patient ID (e.g., 'PAT-101' or ABHA ID)")
    session_id: Optional[str] = Field(None, description="Active dialogue session ID if captured during kiosk intake")
    document_type: DocumentType = Field(default=DocumentType.PRESCRIPTION, description="Clinical categorization")
    original_filename: str = Field(default="document.jpg", description="Original client-side filename")


class StoredDocumentResult(BaseModel):
    """
    Complete record returned after document optimization, storage upload, and DB registration.
    """
    id: str = Field(..., description="Unique document UUID")
    patient_id: str = Field(..., description="Patient ID")
    session_id: Optional[str] = Field(None, description="Associated kiosk session ID")
    document_type: DocumentType = Field(..., description="Document type")
    
    # Storage Pointers & Presigned Temporary Access URLs
    storage_bucket: str = Field(..., description="Object storage bucket name")
    file_path_raw: Optional[str] = Field(None, description="Storage path to uncompressed raw archival file")
    file_path_processed: str = Field(..., description="Storage path to normalized high-res WebP")
    file_path_thumbnail: str = Field(..., description="Storage path to 300px preview WebP")
    
    signed_url_processed: Optional[str] = Field(None, description="15-minute temporary presigned viewing URL")
    signed_url_thumbnail: Optional[str] = Field(None, description="15-minute temporary presigned thumbnail URL")
    signed_url_raw: Optional[str] = Field(None, description="15-minute temporary presigned raw download URL")
    
    # Forensic Integrity
    file_hash_sha256: str = Field(..., description="SHA-256 checksum")
    perceptual_hash_dhash: Optional[str] = Field(None, description="Perceptual dHash")
    file_size_bytes: int = Field(..., description="Raw file size in bytes")
    mime_type: str = Field(..., description="MIME type")
    
    # Lifecycle & Quality
    ocr_status: OCRStatus = Field(default=OCRStatus.PENDING, description="OCR extraction status")
    quality_score: float = Field(default=100.0, description="Quality score 0-100")
    sharpness_score: float = Field(default=0.0, description="Sharpness variance")
    is_duplicate_linked: bool = Field(default=False, description="True if linked to an existing scan")
    
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    
    model_config = ConfigDict(from_attributes=True)
