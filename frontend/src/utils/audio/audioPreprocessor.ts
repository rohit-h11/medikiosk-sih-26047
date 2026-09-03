/**
 * MediKiosk Clinical Audio Preprocessor & DSP Pipeline
 * Preprocesses patient voice recordings for optimal speech recognition accuracy (Whisper / Bhashini / Sarvam):
 * 1. DC Offset Removal
 * 2. High-Quality 16kHz Resampling
 * 3. STFT Spectral Subtraction (eliminates fan noise, motor hum, and air turbulence hiss)
 * 4. Adaptive Downward Noise Gate (ensures clean silence during pauses between words)
 * 5. Silence & Dead-Air Trimming with Pre/Post Safety Padding
 * 6. Noise-Aware Peak Normalization (-0.9 dBFS)
 * 7. VAD Speech Energy Validation
 * 8. 16-Bit Linear PCM WAV Container Encoding
 */

import { AudioProcessingConfig, AudioPreprocessingStats, ProcessedAudioResult } from '@/types/audio';
import { encodeWAV } from './wavEncoder';
import { calculateRms, detectSpeechInBuffer, linearToDbfs } from './vad';
import { spectralSubtractNoise } from './spectralSubtraction';
import { applyNoiseGate } from './noiseGate';

const DEFAULT_CONFIG: Required<AudioProcessingConfig> = {
  targetSampleRate: 16000,
  noiseSuppression: true,
  echoCancellation: true,
  autoGainControl: false, // Prevents browser hardware from auto-cranking fan noise
  enableHighPassFilter: true,
  highPassCutoff: 110,
  enableCompression: false,
  enableSpectralDenoise: true,
  spectralDenoiseStrength: 1.0,
  enableNoiseGate: false,
  noiseGateThreshold: 0.007,
  trimSilence: true,
  silenceRmsThreshold: 0.007,
  silencePaddingSec: 0.20,
  normalizePeak: false, // Prevents post-processing from artificially boosting background fan noise
  targetPeak: 0.90,
  minDurationMs: 350,
  maxDurationMs: 30000,
};

/**
 * Removes baseline DC offset (drifting mean) from audio samples.
 */
export function removeDcOffset(samples: Float32Array): Float32Array {
  if (samples.length === 0) return samples;
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i];
  }
  const mean = sum / samples.length;
  const result = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    result[i] = samples[i] - mean;
  }
  return result;
}

/**
 * High-quality band-limited resampling converting any audio sample rate down to target sample rate (default 16000 Hz).
 * Includes box-car/anti-aliasing integration for downsampling.
 */
export function resampleAudio(
  samples: Float32Array,
  inputRate: number,
  targetRate: number = 16000
): Float32Array {
  if (inputRate === targetRate || samples.length === 0) {
    return new Float32Array(samples);
  }

  const ratio = inputRate / targetRate;
  const outputLength = Math.round(samples.length / ratio);
  const result = new Float32Array(outputLength);

  if (ratio > 1) {
    // Downsampling: Use windowed averaging to prevent aliasing
    for (let i = 0; i < outputLength; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.min(Math.floor((i + 1) * ratio), samples.length);
      let sum = 0;
      let count = 0;
      for (let j = start; j < end; j++) {
        sum += samples[j];
        count++;
      }
      result[i] = count > 0 ? sum / count : 0;
    }
  } else {
    // Upsampling: Linear interpolation
    for (let i = 0; i < outputLength; i++) {
      const position = i * ratio;
      const index = Math.floor(position);
      const fraction = position - index;
      const sample1 = samples[index] || 0;
      const sample2 = samples[index + 1] !== undefined ? samples[index + 1] : sample1;
      result[i] = sample1 + fraction * (sample2 - sample1);
    }
  }

  return result;
}

/**
 * Trims leading and trailing silence from the audio buffer based on RMS energy threshold.
 * Keeps a configurable padding margin (e.g. 150ms) to ensure first/last consonants are preserved.
 */
export function trimSilence(
  samples: Float32Array,
  sampleRate: number,
  threshold: number = 0.015,
  paddingSec: number = 0.15
): { trimmed: Float32Array; startSec: number; endSec: number; trimmedSec: number } {
  if (samples.length === 0) {
    return { trimmed: samples, startSec: 0, endSec: 0, trimmedSec: 0 };
  }

  const frameSize = Math.floor(sampleRate * 0.02); // 20ms frames
  const totalFrames = Math.floor(samples.length / frameSize);
  if (totalFrames === 0) {
    return { trimmed: samples, startSec: 0, endSec: samples.length / sampleRate, trimmedSec: 0 };
  }

  let startFrame = -1;
  let endFrame = -1;

  // 1. Scan forward for voice onset
  for (let i = 0; i < totalFrames; i++) {
    const frame = samples.subarray(i * frameSize, (i + 1) * frameSize);
    const rms = calculateRms(frame);
    if (rms >= threshold) {
      startFrame = i;
      break;
    }
  }

  // If no speech found, return original buffer
  if (startFrame === -1) {
    return {
      trimmed: samples,
      startSec: 0,
      endSec: samples.length / sampleRate,
      trimmedSec: 0,
    };
  }

  // 2. Scan backward for voice offset
  for (let i = totalFrames - 1; i >= startFrame; i--) {
    const frame = samples.subarray(i * frameSize, (i + 1) * frameSize);
    const rms = calculateRms(frame);
    if (rms >= threshold) {
      endFrame = i;
      break;
    }
  }

  if (endFrame === -1) {
    endFrame = totalFrames - 1;
  }

  // 3. Apply padding margin in samples
  const paddingSamples = Math.floor(paddingSec * sampleRate);
  const startIndex = Math.max(0, startFrame * frameSize - paddingSamples);
  const endIndex = Math.min(samples.length, (endFrame + 1) * frameSize + paddingSamples);

  const trimmed = samples.slice(startIndex, endIndex);
  const originalDuration = samples.length / sampleRate;
  const trimmedDuration = trimmed.length / sampleRate;

  return {
    trimmed,
    startSec: startIndex / sampleRate,
    endSec: endIndex / sampleRate,
    trimmedSec: Math.max(0, originalDuration - trimmedDuration),
  };
}

/**
 * Normalizes peak amplitude with smart noise-floor awareness to prevent amplifying residual room noise.
 */
export function normalizePeak(
  samples: Float32Array,
  targetPeak: number = 0.90
): { normalized: Float32Array; peak: number; gainApplied: number } {
  if (samples.length === 0) {
    return { normalized: samples, peak: 0, gainApplied: 1.0 };
  }

  let maxPeak = 0;
  for (let i = 0; i < samples.length; i++) {
    const absVal = Math.abs(samples[i]);
    if (absVal > maxPeak) {
      maxPeak = absVal;
    }
  }

  if (maxPeak < 0.005) {
    // Audio is pure silence / noise floor, do not amplify
    return { normalized: new Float32Array(samples), peak: maxPeak, gainApplied: 1.0 };
  }

  // Smart gain: cap digital boost at 4.0x (+12dB) to prevent over-boosting noise floor
  const gain = Math.min(targetPeak / maxPeak, 4.0);
  const normalized = new Float32Array(samples.length);

  for (let i = 0; i < samples.length; i++) {
    normalized[i] = Math.max(-1.0, Math.min(1.0, samples[i] * gain));
  }

  return {
    normalized,
    peak: maxPeak * gain,
    gainApplied: gain,
  };
}

/**
 * Master audio preprocessing pipeline for Push-to-Talk recordings.
 */
export function preprocessAudio(
  rawSamples: Float32Array,
  sourceSampleRate: number,
  options?: AudioProcessingConfig
): ProcessedAudioResult {
  const config = { ...DEFAULT_CONFIG, ...options };
  const originalDurationSec = rawSamples.length / sourceSampleRate;

  // Step 1: Remove DC offset
  let processed = removeDcOffset(rawSamples);

  // Step 2: Resample to target sample rate (default 16kHz)
  const targetRate = config.targetSampleRate || 16000;
  processed = resampleAudio(processed, sourceSampleRate, targetRate);

  // Step 3: Smooth Decision-Directed Wiener Spectral Noise Reduction
  if (config.enableSpectralDenoise) {
    processed = spectralSubtractNoise(processed, {
      suppressionStrength: config.spectralDenoiseStrength ?? 1.0,
      minGainFloor: 0.08,
      frameSize: 512,
      hopSize: 256,
    });
  }

  // Step 4: Optional Adaptive Downward Noise Gate
  if (config.enableNoiseGate) {
    processed = applyNoiseGate(processed, targetRate, {
      threshold: config.noiseGateThreshold ?? 0.007,
      floorGain: 0.05,
      attackSec: 0.005,
      releaseSec: 0.120, // 120ms release to prevent word clipping
    });
  }

  // Step 5: Silence & dead-air trimming
  let silenceTrimmedSec = 0;
  if (config.trimSilence) {
    const trimResult = trimSilence(
      processed,
      targetRate,
      config.silenceRmsThreshold,
      config.silencePaddingSec
    );
    processed = trimResult.trimmed;
    silenceTrimmedSec = trimResult.trimmedSec;
  }

  // Step 6: Noise-aware peak amplitude normalization
  let peak = 0;
  if (config.normalizePeak) {
    const normResult = normalizePeak(processed, config.targetPeak);
    processed = normResult.normalized;
    peak = normResult.peak;
  } else {
    for (let i = 0; i < processed.length; i++) {
      const absVal = Math.abs(processed[i]);
      if (absVal > peak) peak = absVal;
    }
  }

  // Step 7: Voice Activity Detection (VAD) verification
  const vadResult = detectSpeechInBuffer(
    processed,
    targetRate,
    0.08,
    config.silenceRmsThreshold
  );

  // Step 8: Encode into 16-bit Linear PCM WAV Blob
  const wavBlob = encodeWAV(processed, targetRate, 1, 16);
  const previewUrl = URL.createObjectURL(wavBlob);
  const rmsEnergy = calculateRms(processed);
  const finalDurationSec = processed.length / targetRate;

  const stats: AudioPreprocessingStats = {
    originalSampleRate: sourceSampleRate,
    targetSampleRate: targetRate,
    originalDurationSec,
    processedDurationSec: finalDurationSec,
    silenceTrimmedSec,
    peakAmplitude: peak,
    peakDbfs: linearToDbfs(peak),
    rmsEnergy,
    byteLength: wavBlob.size,
    hasSpeech: vadResult.hasSpeech,
  };

  return {
    blob: wavBlob,
    pcmSamples: processed,
    stats,
    previewUrl,
  };
}
