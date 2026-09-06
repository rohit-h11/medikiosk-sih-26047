# backend/app/ai/dialogue/protocols/registry.py
"""
MediKiosk — Protocol Registry & Factory
Provides zero-if plug-and-play registration and lookup for clinical strategies.
"""

from typing import Dict, Type, Optional
import logging
from app.ai.dialogue.protocols.base import ClinicalProtocol

logger = logging.getLogger("medikiosk.protocols.registry")

_REGISTRY: Dict[str, Type[ClinicalProtocol]] = {}

def register_protocol(name: str):
    """Class decorator to register a medical strategy."""
    def decorator(cls: Type[ClinicalProtocol]):
        key = name.lower().strip()
        _REGISTRY[key] = cls
        logger.info(f"Registered clinical protocol strategy: '{key}' -> {cls.__name__}")
        return cls
    return decorator

def get_protocol(hospital_type: Optional[str] = None) -> ClinicalProtocol:
    """
    Factory function to retrieve protocol instance based on hospital type / department.
    Defaults to 'allopathy' if unspecified.
    """
    raw_key = (hospital_type or "allopathy").lower().strip()
    
    # Alias mappings
    alias_map = {
        "ayurveda": "ayurveda",
        "ayush": "ayurveda",
        "kayachikitsa": "ayurveda",
        "allopathy": "allopathy",
        "general": "allopathy",
        "mbbs": "allopathy",
        "general medicine": "allopathy",
        "emergency": "allopathy"
    }
    
    target_key = alias_map.get(raw_key, "allopathy")
    protocol_cls = _REGISTRY.get(target_key, _REGISTRY.get("allopathy"))
    
    if not protocol_cls:
        # Fallback if registry not populated yet
        from app.ai.dialogue.protocols.allopathy import AllopathyProtocol
        return AllopathyProtocol()
        
    return protocol_cls()
