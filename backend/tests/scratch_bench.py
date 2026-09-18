import sys
sys.stdout.reconfigure(encoding='utf-8')
import asyncio, time, httpx, json

BASE_URL = 'http://127.0.0.1:8000/api/v1'

async def test():
    t0 = time.time()
    timeline = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        form_data = {
            'session_id': f'bench_sess_{int(time.time())}',
            'patient_id': '91-8824-3942-1092',
            'hospital_type': 'allopathy',
            'language': 'hi',
            'text_response': 'गर्मी से ये ज़्यादा होता है।',
            'max_turns': '10'
        }
        async with client.stream('POST', f'{BASE_URL}/interview/stream', data=form_data) as response:
            buffer = ''
            async for chunk in response.aiter_text():
                buffer += chunk
                while '\n\n' in buffer:
                    block, buffer = buffer.split('\n\n', 1)
                    for line in block.strip().splitlines():
                        if line.startswith('data:'):
                            data = json.loads(line[5:].strip())
                            elapsed = round(time.time() - t0, 2)
                            evt = data.get('event')
                            timeline.append((evt, elapsed))
                            if evt == 'transcription':
                                print(f"[{elapsed}s] 1. Transcription confirmed: {data.get('native')}")
                            elif evt == 'text_chunk':
                                print(f"[{elapsed}s] 2. Question appears on screen: {data.get('text')}")
                            elif evt == 'touch_options':
                                print(f"[{elapsed}s] 3. Touch pills clickable: {len(data.get('touch_options', []))} options")
                            elif evt == 'audio_chunk':
                                print(f"[{elapsed}s] 4. Voice starts speaking through speakers")
                            elif evt == 'done':
                                print(f"[{elapsed}s] 5. Turn completed")

    print('\n=== EXACT PATIENT PERCEPTION TIMELINE ===')
    for evt, t in timeline:
        print(f"  {evt:15}: {t}s")

if __name__ == '__main__':
    asyncio.run(test())
