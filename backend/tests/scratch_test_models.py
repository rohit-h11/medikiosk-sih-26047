import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv('.env')

async def test_groq():
    key = os.getenv('GROQ_API_KEY')
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    models = ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'openai/gpt-oss-20b', 'qwen/qwen3.6-27b']
    for m in models:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post('https://api.groq.com/openai/v1/chat/completions', headers=headers, json={
                    'model': m,
                    'messages': [{'role': 'user', 'content': 'Respond with valid JSON: {"hello": "world"}'}],
                    'response_format': {'type': 'json_object'}
                })
                print(m, res.status_code, res.text[:120] if res.status_code != 200 else res.json()['choices'][0]['message']['content'])
        except Exception as e:
            print(m, 'error:', e)

asyncio.run(test_groq())
