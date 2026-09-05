# MediKiosk Voice & API Latency Optimization Blueprint

**Project:** MediKiosk (Smart India Hackathon 2026 · Problem Statement 26047)  
**Target:** Reducing End-to-End Voice Turnaround Latency from **5–6 seconds down to <1.8 seconds**  
**Audience:** Backend, Dialogue Engine, and Audio DSP Engineers  

---

## 1. Executive Summary

In a high-volume Indian hospital Outpatient Department (OPD) kiosk, conversational voice latency is the single most critical factor for user experience. If a patient speaks into the microphone and waits **5 to 6 seconds** in silence before hearing an answer, they assume the kiosk has crashed, talk over the system, or become disengaged.

This blueprint analyzes why the current turnaround is 5–6 seconds and provides **5 concrete engineering optimizations** to cut perceived latency down to **sub-1.5–1.8 seconds**.

---

## 2. Root Cause: The "Sequential Waterfall" Problem

Currently, every dialogue turn executes in a strict, single-threaded waterfall sequence:

```
[ Patient Stops Speaking ]
  ├── 1. Bhashini ASR (Speech-to-Text):           ~1.2s  (Waiting...)
  ├── 2. Bhashini NMT (Native -> English):        ~0.8s  (Waiting...)
  ├── 3. Embedding Generation + Supabase RAG RPC: ~0.6s  (Waiting...)
  ├── 4. LLM Generation (Waiting for full text):  ~2.0s  (Waiting...)
  ├── 5. Bhashini NMT (English -> Native):        ~0.8s  (Waiting...)
  └── 6. Bhashini TTS (Full Audio Synthesis):     ~1.2s  (Waiting...)
  ─────────────────────────────────────────────────────────────
  TOTAL SEQUENTIAL TIME LAG:                      ~6.6 SECONDS 😴
```

Each stage must finish 100% of its work before the next stage even begins.

---

## 3. The 5 Core Optimization Strategies

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               OPTIMIZATION MATRIX                               │
├───────────────────────────────────────────────────────┬──────────────┬──────────┤
│ Optimization Technique                                │ Latency Gain │ Priority │
├───────────────────────────────────────────────────────┼──────────────┼──────────┤
│ 1. First-Sentence Streaming & Audio Pipelining        │ -2,500 ms    │ P0 (Top) │
│ 2. Ultra-Fast LLM Inference Engine (Groq/Gemini Flash)│ -1,200 ms    │ P0 (Top) │
│ 3. Selective / Conditional RAG Retrieval              │ -500 ms      │ P1       │
│ 4. Asynchronous Parallel Fan-Out (`asyncio.gather`)   │ -400 ms      │ P1       │
│ 5. Persistent HTTP Connection Pooling (Keep-Alive)    │ -600 ms      │ P1       │
└───────────────────────────────────────────────────────┴──────────────┴──────────┘
```

---

### Strategy 1: First-Sentence Streaming & Audio Pipelining (The Game Changer)

#### The Problem:
Waiting for the LLM to finish generating an entire 3-sentence response (30–40 words) before starting translation and audio synthesis wastes **~3.5 seconds**.

#### The Solution (Token-to-Sentence Buffer):
1. Call the LLM with `stream=True`.
2. Accumulate incoming tokens in a small buffer until a sentence delimiter is hit:
   - Delimiters: `.` (period), `?` (question), `!` (exclamation), `\n` (newline), or `।` (Devanagari Danda).
3. As soon as **Sentence 1** (first 5–7 words, ~250ms into LLM generation) is detected:
   - Send Sentence 1 immediately to Translation & Text-to-Speech (TTS).
4. **The Overlap Illusion**:
   - Sentence 1 takes ~1.5 to 2.0 seconds to play out loud on the kiosk speakers.
   - While the patient is listening to Sentence 1, the LLM finishes generating Sentences 2 and 3 in the background!
   - Sentence 2 is already buffered and plays with **0ms silence** between sentences.

```
Time (sec): 0.0s    0.3s    0.6s    0.9s    1.2s    1.5s    1.8s    2.1s    2.4s
LLM Stream: [Sentence 1] -> [Sentence 2] -> [Sentence 3] (Finished)
Audio Play:                 [▶️ Play Sentence 1] -> [▶️ Play Sentence 2] -> [▶️ Play 3]
Patient:                    "नमस्ते, मैं..."         "क्या आपको..."       "कृपया..."
```

---

### Strategy 2: Ultra-Fast LLM Inference (Groq / Gemini 2.0 Flash)

#### The Problem:
Standard OpenAI GPT-4 or unoptimized local models take 1.5–2.5s for Time-to-First-Token (TTFT).

#### The Solution:
Use ultra-high-throughput LPU / specialized inference engines:
- **Groq Cloud** (running `llama-3.3-70b-versatile` or `llama-3.1-8b-instant` at **300–800 tokens/second**).
- **Google Gemini 2.0 Flash** (sub-200ms TTFT).
- **Result:** Time-to-first-token drops from 2,000ms down to **~150–250ms**.

---

### Strategy 3: Selective / Conditional RAG Retrieval

#### The Problem:
Currently, the backend converts *every user utterance* into a 384-dimensional vector and runs an RPC similarity search against Supabase—even when the patient simply says:
- *"हाँ"* (Yes)
- *"नहीं"* (No)
- *"नमस्ते"* (Hello)
- *"2 दिन से"* (For 2 days)

#### The Solution:
Only trigger vector generation and database search when the utterance contains **clinical trigger entities** (symptoms, body parts, drug names, diseases) or is longer than 4 words.
- Short affirmations (< 4 words with no new medical noun) **skip RAG retrieval entirely**.
- **Result:** Saves **400–600ms** on more than 60% of all conversation turns.

---

### Strategy 4: Asynchronous Parallel Fan-Out (`asyncio.gather`)

#### The Problem:
Running independent database reads and safety scans in a sequential line:
```
Wait for RAG (400ms) -> Then wait for Session State (300ms) -> Then wait for Red-Flags (50ms) = 750ms
```

#### The Solution:
In Python, fire all non-dependent async tasks concurrently using `asyncio.gather()` (the Python equivalent of JavaScript's `Promise.all()`):

```
                       ┌──► Task A: Fetch Session / SOCRATES State
                       │
[ Incoming Utterance ] ├──► Task B: Run RAG Search (if clinical)
                       │
                       └──► Task C: Run Tier-1 Red-Flag Regex Scan
```

- **Result:** All three tasks complete in the time taken by the single slowest task (**~400ms instead of 750ms**).

---

### Strategy 5: Persistent HTTP Connection Pooling (Keep-Alive)

#### The Problem:
Creating a new HTTP client on every API turn forces a new **TCP Handshake + SSL/TLS Certificate Exchange** for every single request to Bhashini, Supabase, and the LLM provider.
- Each TLS handshake costs **150–250ms** of pure network delay.
- Across 3 API calls per turn, you lose up to **800ms** just establishing encrypted connections.

#### The Solution:
Instantiate a single global `httpx.AsyncClient` with `keep_alive = True` and connection pooling when the FastAPI app starts up:
- Reuses already open, warm, encrypted TLS sockets.
- Eliminates DNS resolution and TLS renegotiation on subsequent turns.
- **Result:** Saves **~400–600ms** per turn.

---

## 4. Before vs. After Latency Comparison

```
+-----------------------------------------------------------------------------------+
| PIPELINE STAGE                          | UNOPTIMIZED (CURRENT) | OPTIMIZED TARGET|
+-----------------------------------------------------------------------------------+
| 1. Bhashini Speech-to-Text (ASR)        | 1,200 ms              | 800 ms          |
| 2. Red-Flag & Session Fan-Out           | 750 ms (Sequential)   | 50 ms (Parallel)|
| 3. RAG Retrieval                        | 600 ms (Always on)    | 0 ms (Skipped)  |
| 4. LLM Time to First Sentence (Groq)    | 2,000 ms (Full text)  | 250 ms (Stream) |
| 5. First Sentence Audio Synthesis (TTS) | 1,200 ms (Full audio) | 350 ms (Chunk 1)|
| 6. HTTP TLS Handshake Overhead          | 600 ms (New clients)  | 0 ms (Pooled)   |
+-----------------------------------------------------------------------------------+
| ⏱️ TOTAL PERCEIVED TIME TO FIRST VOICE  | ~6,350 ms (~6.3 sec)  | ~1,450 ms (1.4s)|
+-----------------------------------------------------------------------------------+
```

---

## 5. Implementation Roadmap

1. **Step 1 (Immediate Quick Win - 30 mins):**  
   Configure persistent `httpx.AsyncClient` and connection pooling in `app/ai/dialogue/llm_client.py`.
2. **Step 2 (Immediate Quick Win - 1 hour):**  
   Add a simple heuristic check in `interview.py` to skip RAG embedding on short conversational affirmations (`"yes"`, `"no"`, `"ok"`).
3. **Step 3 (Core Architectural Upgrade):**  
   Switch LLM inference provider to Groq / Gemini 2.0 Flash with streaming enabled.
4. **Step 4 (Audio Pipelining):**  
   Implement the Token-to-Sentence buffer accumulator to stream audio chunk-by-chunk to the frontend Web Audio player.

---

## 6. Conclusion

By shifting from a **sequential waterfall** to **pipelined streaming and parallel fan-out**, MediKiosk delivers a fast, responsive, and natural conversational experience worthy of a winning SIH submission.
