# backend/app/ai/dialogue/protocols/__init__.py
from app.ai.dialogue.protocols.base import ClinicalProtocol
from app.ai.dialogue.protocols.registry import register_protocol, get_protocol
from app.ai.dialogue.protocols.allopathy import AllopathyProtocol
from app.ai.dialogue.protocols.ayurveda import AyurvedaProtocol

__all__ = [
    "ClinicalProtocol",
    "register_protocol",
    "get_protocol",
    "AllopathyProtocol",
    "AyurvedaProtocol"
]
