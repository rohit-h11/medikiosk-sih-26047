# backend/tests/test_full_kiosk_lifecycle.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_allopathy_turn():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Initial turn in Allopathy
        res = await client.post(
            "/api/v1/interview/turn",
            data={
                "session_id": "test_allo_sess_01",
                "patient_id": "PAT-TEST-ALLO",
                "hospital_type": "allopathy",
                "language": "en",
                "text_response": "I have severe sharp chest pain since yesterday"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["phase"] == "DYNAMIC_SOCRATES"
        assert data["session_id"] == "test_allo_sess_01"
        assert len(data["touch_options"]) > 0

@pytest.mark.asyncio
async def test_ayurveda_full_kiosk_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = "test_ayu_sess_01"
        
        # Turn 1: Starts in Prakriti assessment Phase, serves Q1
        res1 = await client.post(
            "/api/v1/interview/turn",
            data={
                "session_id": session_id,
                "patient_id": "PAT-TEST-AYU-01",
                "hospital_type": "ayurveda",
                "language": "en",
                "text_response": "Hello"
            }
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["phase"] == "PRAKRITI"
        assert data1["turn_number"] == 1
        assert "Which best describes your natural body build" in data1["next_question"]["english"]
        assert len(data1["touch_options"]) == 3

        # Answer Q1 through Q11 (11 requests serving Q2 through Q12)
        for i in range(1, 12):
            res = await client.post(
                "/api/v1/interview/turn",
                data={
                    "session_id": session_id,
                    "patient_id": "PAT-TEST-AYU-01",
                    "hospital_type": "ayurveda",
                    "language": "en",
                    "selected_option_id": "B" # Pitta options
                }
            )
            assert res.status_code == 200

        # Request 13 (Answering Q12) -> Calculates Prakriti and serves Dashavidha Q1!
        res13 = await client.post(
            "/api/v1/interview/turn",
            data={
                "session_id": session_id,
                "patient_id": "PAT-TEST-AYU-01",
                "hospital_type": "ayurveda",
                "language": "en",
                "selected_option_id": "B"
            }
        )
        assert res13.status_code == 200
        data13 = res13.json()
        assert data13["phase"] == "DASHAVIDHA"
        assert data13["prakriti_result"] is not None
        assert "Pittaja" in data13["prakriti_result"]["prakriti_type"]
        assert "When dealing with physical pain" in data13["next_question"]["english"]


@pytest.mark.asyncio
async def test_sse_stream_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/interview/stream",
            data={
                "session_id": "test_sse_stream_01",
                "patient_id": "PAT-TEST-SSE",
                "hospital_type": "ayurveda",
                "language": "en",
                "text_response": "Hello"
            }
        )
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body_text = res.text
        assert '"event": "transcription"' in body_text
        assert '"event": "text_chunk"' in body_text
        assert '"event": "touch_options"' in body_text
        assert '"event": "done"' in body_text

