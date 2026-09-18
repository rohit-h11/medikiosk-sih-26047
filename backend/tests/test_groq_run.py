import os
import sys
import time
from dotenv import load_dotenv
from groq import Groq
from google import genai

load_dotenv("backend/.env")

# 1. Test Gemini 3.6 Flash
print("--- Testing Gemini 3.6 Flash ---", flush=True)
gemini_key = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=gemini_key)
t0 = time.time()
try:
    g_res = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents="Generate a clean 50-word medical JSON summary: {\"status\": \"ok\", \"note\": \"...\"}"
    )
    print(f"Gemini 3.6 Flash SUCCESS ({round(time.time()-t0, 2)}s):\n{g_res.text}\n", flush=True)
except Exception as e:
    print(f"Gemini failed: {e}\n", flush=True)

# 2. Test Groq with max_tokens
print("--- Testing Groq with max_tokens ---", flush=True)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
for model in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
    t0 = time.time()
    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Return JSON: {\"status\": \"ok\"}"}],
            max_tokens=200,
            temperature=0.1
        )
        print(f"Groq {model} SUCCESS ({round(time.time()-t0, 2)}s):\n{resp.choices[0].message.content}\n", flush=True)
    except Exception as e:
        print(f"Groq {model} failed: {e}\n", flush=True)
