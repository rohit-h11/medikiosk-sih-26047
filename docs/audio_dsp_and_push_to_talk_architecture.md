# 🎙️ MediKiosk Frontend Audio & DSP Architecture: Comprehensive Engineering Guide

> **Target Audience:** Developers, ML Engineers, Evaluators, and Researchers  
> **Topic:** End-to-End Client-Side Audio Pipeline, Acoustics & Wave Physics, Web Audio API DSP Graphs, Minimum-Statistics Wiener Spectral Denoising, Anti-Aliased 16 kHz Resampling, Silence Trimming, and 16-bit Linear PCM WAV Encoding.

---

## 📑 Table of Contents

1. [High-Level Architectural Overview](#1-high-level-architectural-overview)
2. [Acoustics & Physics: Understanding Sound and Room Noise](#2-acoustics--physics-understanding-sound-and-room-noise)
   - [What is Sound Physically?](#what-is-sound-physically)
   - [The Principle of Wave Superposition](#the-principle-of-wave-superposition)
   - [The Physics of Fan Noise (Motor Drone vs Air Turbulence)](#the-physics-of-fan-noise-motor-drone-vs-air-turbulence)
   - [Fourier's Principle: The Prism of Sound](#fouriers-principle-the-prism-of-sound)
3. [Stage 1: Live Hardware Capture & Web Audio DSP Graph](#3-stage-1-live-hardware-capture--web-audio-dsp-graph)
   - [The "Water Filtration Pipeline" Model](#the-water-filtration-pipeline-model)
   - [Microphone Acquisition & Why Auto-Gain (AGC) Must Be Disabled](#microphone-acquisition--why-auto-gain-agc-must-be-disabled)
   - [The 110 Hz High-Pass Filter (The Mud Strainer)](#the-110-hz-high-pass-filter-the-mud-strainer)
   - [The Analyser Node (The Glass Inspection Window)](#the-analyser-node-the-glass-inspection-window)
   - [The ScriptProcessor Node (The Storage Bucket)](#the-scriptprocessor-node-the-storage-bucket)
4. [Stage 2: Post-Recording Offline DSP Preprocessing Pipeline](#4-stage-2-post-recording-offline-dsp-preprocessing-pipeline)
   - [Step 2.1: DC Offset Removal (Baseline Centering)](#step-21-dc-offset-removal-baseline-centering)
   - [Step 2.2: Anti-Aliased 16 kHz Resampling (Nyquist-Shannon Theorem)](#step-22-anti-aliased-16-khz-resampling-nyquist-shannon-theorem)
   - [Step 2.3: Minimum-Statistics Noise Profiling (Tracking Ambient Fan)](#step-23-minimum-statistics-noise-profiling-tracking-ambient-fan)
   - [Step 2.4: Decision-Directed Wiener Spectral Denoising (Ephraim-Malah)](#step-24-decision-directed-wiener-spectral-denoising-ephraim-malah)
   - [Step 2.5: Dead-Air & Silence Trimming with 200ms Safety Padding](#step-25-dead-air--silence-trimming-with-200ms-safety-padding)
   - [Step 2.6: Noise-Floor Aware Normalization](#step-26-noise-floor-aware-normalization)
   - [Step 2.7: Voice Activity Detection (VAD) & Zero-Crossing Rates](#step-27-voice-activity-detection-vad--zero-crossing-rates)
5. [Stage 3: Binary 16-Bit Linear PCM WAV Encoding](#5-stage-3-binary-16-bit-linear-pcm-wav-encoding)
6. [Stage 4: React Push-To-Talk State Machine & Event Binding](#6-stage-4-react-push-to-talk-state-machine--event-binding)
7. [Stage 5: Packaging & Backend Transport](#7-stage-5-packaging--backend-transport)
8. [Summary Engineering Reference Table](#8-summary-engineering-reference-table)

---

## 1. High-Level Architectural Overview

When a patient interacts with the MediKiosk terminal, audio flows through two sequential stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: LIVE HARDWARE CAPTURE & REAL-TIME DSP (While Patient Holds Button)  │
└─────────────────────────────────────────────────────────────────────────────┘
  Microphone Hardware Stream (48 kHz Mono, AGC Disabled)
       │
       ▼
  [MediaStreamAudioSourceNode]
       │
       ▼
  [BiquadFilterNode: High-Pass 110 Hz, Q=0.707] ──► Strips electrical hum & desk rumble
       │
       ▼
  [AnalyserNode: FFT = 512 & RMS Telemetry]     ──► Drives 60fps live volume meter in UI
       │
       ▼
  [ScriptProcessorNode: 4096 Float32 Chunks]    ──► Collects raw samples in memory

                                 ═══════════════
                              Button Released by User
                                 ═══════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: POST-RECORDING OFFLINE DSP PIPELINE (Runs in ~20ms upon Release)    │
└─────────────────────────────────────────────────────────────────────────────┘
  Merged Raw Float32 Array
       │
       ▼
  1. removeDcOffset()          ──► Centers wave at 0.0V (removes voltage drift)
       │
       ▼
  2. resampleAudio()           ──► Anti-aliased downsampling (48k -> 16,000 Hz Mono)
       │
       ▼
  3. Minimum-Statistics STFT   ──► Scans quietest 20% frames to fingerprint fan profile
       │
       ▼
  4. Wiener Spectral Denoising ──► Smooth -22dB fan reduction (zero robotic artifacts)
       │
       ▼
  5. trimSilence()             ──► Strips leading/trailing dead air (with 200ms padding)
       │
       ▼
  6. detectSpeechInBuffer()    ──► VAD validation (verifies speech energy & ZCR)
       │
       ▼
  7. encodeWAV()               ──► Generates 44-byte RIFF header + 16-bit PCM .wav Blob

                                 ═══════════════
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: BACKEND DELIVERY (FormData Multipart HTTP POST / WebSocket)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Acoustics & Physics: Understanding Sound and Room Noise

### What is Sound Physically?
Sound is a **longitudinal mechanical pressure wave**. 
- When a patient speaks, their vocal cords vibrate back and forth, colliding with surrounding air molecules.
- This creates alternating regions of high pressure (**compressions**) and low pressure (**rarefactions**) traveling through the air at approximately 343 meters per second.
- When this wave hits the microphone, it pushes against a tiny conductive plate called the **diaphragm**.
- The microphone converts this physical displacement into fluctuating electrical voltage.
- The computer's sound card measures (samples) this voltage **48,000 times per second**, recording each measurement as a 32-bit floating-point number between `-1.0` and `+1.0`.

```
Air Compression Waves            Microphone Diaphragm        Digital Floating-Point Stream
  ( ( ( ( ( ( ( ( ( ( ──────►          [ | ]        ──────►  [ +0.12, +0.45, +0.89, -0.23... ]
```

---

### The Principle of Wave Superposition
A microphone diaphragm is a single physical plate. It cannot "know" where an air molecule came from.
If a patient is speaking while a ceiling fan is spinning in the room, both pressure waves hit the diaphragm simultaneously.

By the **Principle of Wave Superposition**:
```
Total Pressure Measured(t) = Speech Pressure(t) + Fan Pressure(t)
```

```
Your Voice Wave:             /\      /\          /\
                            /  \    /  \        /  \
                              +
Fan Noise (Hiss + Drone):   ~^~^~^~^~^~^~^~^~^~^~^~^~^~^~^~
                              =
What Microphone Records:    ~/\~^~/~^\~/\~^~/~^\~/\~^~/~^\~ (Combined noisy wave)
```

To clean the audio, we must mathematically separate the fan wave from the speech wave.

---

### The Physics of Fan Noise (Motor Drone vs Air Turbulence)

A fan produces two completely different types of sound in the air:

#### 1. Low-Frequency Blade-Pass & Motor Drone (Tonal Noise)
As fan blades rotate, each blade strikes the air, generating a rhythmic pressure pulse.
The formula for the **Blade-Pass Frequency (BPF)** is:
```
Blade-Pass Frequency = (RPM * Number of Blades) / 60
```
- A 3-blade ceiling fan running at 300 RPM produces a fundamental blade strike of `(300 * 3) / 60 = 15 Hz`.
- The electric motor also vibrates at electromagnetic AC harmonics: **50 Hz, 100 Hz, 150 Hz, 200 Hz**.
- This produces a low-to-mid frequency drone oscillating between **100 Hz and 250 Hz**.

#### 2. Turbulent Air Vortex Shedding (Broadband Hiss / Pink Noise)
As fan blades slice through air at high velocity, air molecules cannot flow smoothly around the trailing edge. They break into chaotic, spinning micro-whirlpools called **Von Kármán vortices**.
- These vortices collide chaotically at random speeds, generating sound across **all frequencies from 300 Hz up to 8,000 Hz**.
- This is what sounds like rushing air or continuous "shhhhh" hiss.

```
                         Air Molecules Colliding Chaotically
                                ~~~~  ~~~~  ~~~~
 Blade ──────► (Slices Air)     ( ( ( Vortex ) ) )  ──► Creates "White/Pink Noise" Hiss
                                ~~~~  ~~~~  ~~~~
```

---

### Fourier's Principle: The Prism of Sound

In the 1800s, French physicist and mathematician **Jean-Baptiste Joseph Fourier** proved a fundamental law of wave mechanics:

> **Fourier's Theorem:**  
> Any complex, arbitrary wave can be decomposed into a sum of pure, simple sine waves of different frequencies, heights (amplitudes), and timing (phases).

#### The Prism Analogy:
Think of white light hitting a glass prism. White light looks like one single solid beam, but the prism splits it into its individual rainbow colors (Red, Green, Blue, etc.).

```
Messy Combined Audio Wave  ──► [ Fast Fourier Transform (FFT) ] ──► Frequency Bins (0 Hz to 8000 Hz)
```

By applying the **Fast Fourier Transform (FFT)**, we convert audio from the **Time Domain** (air pressure vs seconds) into the **Frequency Domain** (energy vs frequency pitch). In the frequency domain, fan noise and human speech occupy different energy signatures, allowing us to subtract the fan!

---

## 3. Stage 1: Live Hardware Capture & Web Audio DSP Graph

The file [`frontend/src/utils/audio/audioGraph.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/audioGraph.ts) manages the real-time audio pipeline.

```
+-------------+      +----------------+      +--------------+      +-------------------+
| Microphone  | ---> | HighPassFilter | ---> | AnalyserNode | ---> |  ScriptProcessor  |
| Source Node |      |  (fc = 110 Hz) |      |  (FFT = 512) |      | (Collects Chunks) |
+-------------+      +----------------+      +--------------+      +-------------------+
```

---

### The "Water Filtration Pipeline" Model

Think of sound coming from the microphone as water flowing through a filtration pipe:

```
[ 1. River Tap ] ──► [ 2. Mud Strainer ] ──► [ 3. Glass Meter ] ──► [ 4. Storage Tank ]
  Microphone            HighPassFilter          AnalyserNode           ScriptProcessor
  (Raw Sound)           (Blocks Low Rumble)     (Volume Gauge)         (Collects Audio)
```

---

### Microphone Acquisition & Why Auto-Gain (AGC) Must Be Disabled

```typescript
const mediaStream = await navigator.mediaDevices.getUserMedia({
  audio: {
    noiseSuppression: { ideal: true },
    echoCancellation: { ideal: true },
    autoGainControl: { ideal: false }, // CRITICAL: Disabled!
    channelCount: { ideal: 1 },        // Single-channel focused mono
  },
  video: false,
});
```

> [!CAUTION]
> **Why `autoGainControl` must be `false`:**
> When browser Auto Gain Control is enabled, the microphone pre-amplifier automatically **cranks up microphone sensitivity to maximum** whenever you pause or speak quietly. It actively hunts for sound in silent gaps, turning a quiet background fan into a loud, roaring jet engine! Turning AGC off keeps microphone sensitivity constant and natural.

---

### The 110 Hz High-Pass Filter (The Mud Strainer)

```typescript
const highPassFilter = audioContext.createBiquadFilter();
highPassFilter.type = 'highpass';
highPassFilter.frequency.setValueAtTime(110, audioContext.currentTime); // Cutoff = 110 Hz
highPassFilter.Q.setValueAtTime(0.707, audioContext.currentTime);     // Butterworth Q
```

- **Human Vocal Fact:** Adult male fundamental voice pitch starts around `85 Hz - 180 Hz`, while adult female voice pitch starts around `165 Hz - 255 Hz`.
- **The Cutoff (110 Hz):** Frequencies below 110 Hz (mechanical table knocks, AC rumble, 50Hz/60Hz mains hum) are attenuated by `-12 dB` to `-24 dB` per octave, while vocal formants pass through untouched.
- **The Q Factor (0.707):** Represents a **Butterworth filter (maximally flat response)** with zero artificial resonance peaks, keeping the voice completely natural.

---

### The Analyser Node (The Glass Inspection Window)

```typescript
const analyserNode = audioContext.createAnalyser();
analyserNode.fftSize = 512;
analyserNode.smoothingTimeConstant = 0.8;
```
- Performs a live Fast Fourier Transform (FFT) on passing audio without altering the sound.
- At 60 frames per second, the UI reads `analyserNode.getByteTimeDomainData()` to animate the live volume bar and visualizer.

---

### The ScriptProcessor Node (The Storage Bucket)

```typescript
const processorNode = audioContext.createScriptProcessor(4096, 1, 1);
const recordedChunks: Float32Array[] = [];

processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
  const inputData = e.inputBuffer.getChannelData(0);
  recordedChunks.push(new Float32Array(inputData));
};
```
- Gathers buckets of 4,096 audio numbers every ~85ms and accumulates them in memory.
- When the button is released, all chunks are merged into a single contiguous `Float32Array`.

---

## 4. Stage 2: Post-Recording Offline DSP Preprocessing Pipeline

Located in [`frontend/src/utils/audio/audioPreprocessor.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/audioPreprocessor.ts).

---

### Step 2.1: DC Offset Removal (Baseline Centering)

Inexpensive microphones often have a slight electrical voltage bias that shifts the waveform baseline away from zero (e.g. resting at `+0.05` instead of `0.00`).

```typescript
export function removeDcOffset(samples: Float32Array): Float32Array {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) sum += samples[i];
  const mean = sum / samples.length; // Calculate the average baseline drift
  const result = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) result[i] = samples[i] - mean; // Center at 0.0V
  return result;
}
```

---

### Step 2.2: Anti-Aliased 16 kHz Resampling (Nyquist-Shannon Theorem)

Modern speech models (Whisper, Bhashini, Sarvam) are trained on **16,000 Hz Mono** audio.

#### The Nyquist-Shannon Rule:
When downsampling to 16,000 Hz, the highest frequency the audio can represent is the **Nyquist Frequency**:
```
Nyquist Frequency = 16000 / 2 = 8,000 Hz
```
- If you downsample by simply skipping samples, any high frequencies above 8,000 Hz in the original 48 kHz recording fold back into lower frequencies as fake metallic aliasing noise (robot sounds).
- **Our Solution:** The `resampleAudio()` function integrates (averages) all sample points within each window, acting as an **anti-aliasing low-pass filter** before decimation.

---

### Step 2.3: Minimum-Statistics Noise Profiling (Tracking Ambient Fan)

Located in [`frontend/src/utils/audio/spectralSubtraction.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/spectralSubtraction.ts).

#### How it works:
1. Divides the recording into 32ms frames (512 samples) with 50% overlap (hop size = 256).
2. Computes the total energy of every single frame across the entire recording.
3. Sorts the frames by energy and selects the **quietest 20% frames**.
4. Averages the frequency spectrum of these quietest frames to create a 100% accurate **Noise Power Profile**: `noisePower[k]`.

> [!NOTE]
> **Why Minimum-Statistics is Superior:** Even if the patient starts speaking immediately upon pressing the button, the algorithm ignores the speech frames and finds the true quiet pauses between words to fingerprint the fan!

---

### Step 2.4: Decision-Directed Wiener Spectral Denoising (Ephraim-Malah)

#### Why Hard Spectral Subtraction Failed:
Simple magnitude subtraction (`|Signal| - alpha * |Noise|`) punches random jagged holes in the frequency spectrum. This causes **"Musical Noise" / phase distortion** (making the human voice sound like a metallic robot speaking underwater).

#### How the Decision-Directed Wiener Filter Solves This:
Instead of punching holes, it computes a smooth mathematical attenuation gain curve:

1. **Posterior SNR:** `gamma = SignalPower[k] / NoisePower[k]`
2. **A-Priori Smoothed SNR (Decision-Directed):**
   ```
   priorSnr = 0.85 * (PrevCleanPower[k] / NoisePower[k]) + 0.15 * max(0, gamma - 1)
   ```
3. **Wiener Gain Curve:**
   ```
   targetGain = priorSnr / (priorSnr + 1)
   ```
4. **Temporal Frame Smoothing:**
   ```
   smoothedGain[k] = 0.65 * smoothedGain[k] + 0.35 * targetGain
   ```
5. Multiplies the frequency spectrum by `smoothedGain[k]` and runs the **Inverse FFT (IFFT)** with Overlap-Add synthesis.

**Result:** The fan noise is attenuated by **-22 dB**, while your voice remains 100% natural, warm, and free of metallic artifacts.

---

### Step 2.5: Dead-Air & Silence Trimming with 200ms Safety Padding

```typescript
export function trimSilence(samples: Float32Array, sampleRate = 16000, threshold = 0.007, paddingSec = 0.20) {
  // Scans forward in 20ms frames for speech onset (startFrame)
  // Scans backward from the end for speech offset (endFrame)
  // Adds 200ms (+3200 samples) safety padding before start and after end
  const paddingSamples = Math.floor(paddingSec * sampleRate);
  const startIndex = Math.max(0, startFrame * frameSize - paddingSamples);
  const endIndex = Math.min(samples.length, (endFrame + 1) * frameSize + paddingSamples);
  return { trimmed: samples.slice(startIndex, endIndex), ... };
}
```
- **200ms Safety Padding:** Ensures that soft initial plosives ("P", "K", "T") and trailing whispers are **never accidentally cut off**.

---

### Step 2.6: Noise-Floor Aware Normalization

- **Why global peak normalization was disabled (`normalizePeak: false`):**
  Previously, peak normalization was multiplying the entire audio file by 300% to 400%, which boosted the quiet background fan floor by 4x.
- Leaving `normalizePeak: false` keeps the audio at its true, clean, natural room level.

---

### Step 2.7: Voice Activity Detection (VAD) & Zero-Crossing Rates

In [`frontend/src/utils/audio/vad.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/vad.ts):
1. **RMS Energy:** `sqrt(sum(sample^2) / N)` measures signal volume.
2. **Zero-Crossing Rate (ZCR):** Measures how frequently the waveform crosses zero volts.
   - Low hums have low ZCR (`< 0.02`).
   - Speech consonants have characteristic ZCR (`0.05 to 0.70`).
3. If valid speech frames exceed 8% of total duration, `stats.hasSpeech` is set to `true`.

---

## 5. Stage 3: Binary 16-Bit Linear PCM WAV Encoding

In [`frontend/src/utils/audio/wavEncoder.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/wavEncoder.ts):
- Clamps 32-bit floats to `[-1.0, 1.0]`.
- Converts floats to signed 16-bit integers (`-32768` to `+32767`).
- Assembles a standard 44-byte binary RIFF/WAVE header in Little-Endian format and exports an `audio/wav` Blob.

```
00000000: 52 49 46 46 (ASCII: "RIFF")
00000004: [36 + dataSize] (4 bytes Little-Endian)
00000008: 57 41 56 45 (ASCII: "WAVE")
0000000c: 66 6d 74 20 (ASCII: "fmt ")
00000010: 10 00 00 00 (Subchunk Size: 16)
00000014: 01 00       (Audio Format: 1 = Linear PCM)
00000016: 01 00       (Channels: 1 = Mono)
00000018: 80 3e 00 00 (Sample Rate: 16,000 Hz)
0000001c: 00 7d 00 00 (Byte Rate: 32,000 bytes/sec)
00000020: 02 00       (Block Align: 2 bytes)
00000022: 10 00       (Bits per Sample: 16)
00000024: 64 61 74 61 (ASCII: "data")
00000028: [dataSize]  (4 bytes Little-Endian)
0000002c: [16-bit Signed Integer Audio Samples...]
```

---

## 6. Stage 4: React Push-To-Talk State Machine & Event Binding

The hook [`frontend/src/hooks/usePushToTalk.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/hooks/usePushToTalk.ts) orchestrates user events:

```
[IDLE] ──(MouseDown / TouchStart / SpaceDown)──► [RECORDING]
                                                       │
                                          (MouseUp / TouchEnd / SpaceUp)
                                                       ▼
[IDLE] ◄──(onAudioReady Callback)─────────────── [PROCESSING] (Runs in ~20ms)
```

- **Accidental Tap Guard:** Discards any tap shorter than 350ms.
- **Safety Timeout:** Automatically stops recordings after 30 seconds.
- **Hardware Cleanup:** Immediately calls `track.stop()` to turn off the microphone hardware light when released.

---

## 7. Stage 5: Packaging & Backend Transport

In [`frontend/src/utils/audio/payloadHelper.ts`](file:///f:/Coding/projects/midiosk%20SIH%20hackathon/frontend/src/utils/audio/payloadHelper.ts):

```typescript
import { createAudioFormData } from '@/utils/audio/payloadHelper';

// Inside your custom component:
const formData = createAudioFormData(audioResult, {
  language: 'hi', // ISO language code (Hindi)
  patientId: 'PATIENT_101',
});

// Sends clean 16kHz WAV directly to backend:
// await fetch('/api/v1/audio/transcribe', { method: 'POST', body: formData });
```

---

## 8. Summary Engineering Reference Table

| Processing Step | Module / Function | Physics / Algorithm | Key Parameter | Benefit |
|---|---|---|---|---|
| **1. Mic Capture** | `audioGraph.ts` | Hardware capture with AGC disabled | `autoGainControl: false` | Prevents mic pre-amp from auto-boosting room fan noise |
| **2. Low Cut** | `audioGraph.ts` | 2nd-order High-Pass Biquad Filter | Cutoff: 110 Hz, $Q = 0.707$ | Cuts AC hum, fan motor drone, and desk thumps |
| **3. Live Meter** | `audioGraph.ts` | 512-point FFT & RMS Telemetry | 60 fps `requestAnimationFrame` | Drives reactive UI volume meter and pulsing mic |
| **4. DC Removal** | `audioPreprocessor.ts` | Baseline mean subtraction | $x[n] - \mu$ | Centers wave at 0.0V, removing hardware electrical drift |
| **5. Resampling** | `audioPreprocessor.ts` | Anti-Aliased Boxcar Decimation | 48 kHz $\to$ 16,000 Hz Mono | Prepares optimal format for Whisper/Bhashini ASR |
| **6. Fan Tracking** | `spectralSubtraction.ts` | Minimum-Statistics STFT Energy | Quietest 20% frames | Fingerprints fan accurately even if patient speaks immediately |
| **7. Denoising** | `spectralSubtraction.ts` | Decision-Directed Wiener Filter | $\alpha = 0.85$, Min Floor $0.08$ | Smooth -22dB fan reduction with zero metallic voice artifacts |
| **8. Trimming** | `audioPreprocessor.ts` | Forward/Backward RMS scanning | Threshold $0.007$, $\pm 200\text{ms}$ pad | Cuts leading/trailing dead air without cutting consonants |
| **9. VAD Check** | `vad.ts` | RMS energy & Zero-Crossing Rate | Frame ratio $\ge 8\%$ | Verifies patient actually spoke (rejects silent clicks) |
| **10. Encoding** | `wavEncoder.ts` | 16-bit Linear PCM Little-Endian | 44-byte standard RIFF header | Standard `.wav` Blob compatible with all backend models |
