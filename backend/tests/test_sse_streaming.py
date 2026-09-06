# backend/tests/test_sse_streaming.py
import pytest
import json
from app.ai.ayurveda.question_bank import get_prakriti_question
from app.ai.dialogue.streaming_orchestrator import stream_static_turn_sse, format_sse_event

@pytest.mark.asyncio
async def test_format_sse_event():
    sse_str = await format_sse_event("test_event", {"key": "value"})
    assert sse_str.startswith("data: ")
    assert sse_str.endswith("\n\n")
    data = json.loads(sse_str.replace("data: ", "").strip())
    assert data["event"] == "test_event"
    assert data["key"] == "value"

@pytest.mark.asyncio
async def test_stream_static_turn_sse():
    q = get_prakriti_question(0, lang="hi")
    events = []
    async for chunk in stream_static_turn_sse(q, language="hi"):
        events.append(chunk)
        
    assert len(events) >= 3
    all_content = "".join(events)
    assert "text_chunk" in all_content
    assert "touch_options" in all_content
    assert "done" in all_content
