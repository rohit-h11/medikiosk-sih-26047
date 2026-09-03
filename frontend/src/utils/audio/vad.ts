/**
 * MediKiosk Voice Activity Detection (VAD) & Audio Energy Analyzer
 * Evaluates whether audio buffers or live frames contain human speech versus background noise.
 */

import { VadResult } from '@/types/audio';

/**
 * Calculates the Root Mean Square (RMS) energy of a PCM sample buffer.
 */
export function calculateRms(samples: Float32Array): number {
  if (samples.length === 0) return 0;
  let sumSquares = 0;
  for (let i = 0; i < samples.length; i++) {
    sumSquares += samples[i] * samples[i];
  }
  return Math.sqrt(sumSquares / samples.length);
}

/**
 * Converts linear amplitude (0.0 to 1.0) to decibels relative to full scale (dBFS).
 */
export function linearToDbfs(linear: number): number {
  if (linear <= 0.00001) return -100;
  return 20 * Math.log10(linear);
}

/**
 * Calculates the Zero-Crossing Rate (ZCR) of a buffer.
 * High ZCR with moderate energy often signifies unvoiced speech (s, sh, f, t sounds).
 */
export function calculateZcr(samples: Float32Array): number {
  if (samples.length < 2) return 0;
  let crossings = 0;
  for (let i = 1; i < samples.length; i++) {
    if ((samples[i] >= 0 && samples[i - 1] < 0) || (samples[i] < 0 && samples[i - 1] >= 0)) {
      crossings++;
    }
  }
  return crossings / (samples.length - 1);
}

/**
 * Frame-level VAD check for real-time streaming audio analysis.
 */
export function evaluateFrameVad(
  frameSamples: Float32Array,
  energyThreshold: number = 0.015,
  zcrMin: number = 0.02,
  zcrMax: number = 0.85
): VadResult {
  const energy = calculateRms(frameSamples);
  const zcr = calculateZcr(frameSamples);

  // Speech typically has energy above ambient room floor and ZCR within normal human vocal range
  const isSpeech = energy >= energyThreshold && zcr >= zcrMin && zcr <= zcrMax;

  return {
    isSpeech,
    energy,
  };
}

/**
 * Evaluates full buffer to determine if patient spoke during the push-to-talk recording.
 * Divides buffer into 20ms analysis frames and checks speech frame proportion.
 */
export function detectSpeechInBuffer(
  samples: Float32Array,
  sampleRate: number = 16000,
  minSpeechRatio: number = 0.08,
  energyThreshold: number = 0.015
): { hasSpeech: boolean; speechFrameCount: number; totalFrames: number; speechRatio: number } {
  const frameSize = Math.floor(sampleRate * 0.02); // 20ms frames
  if (samples.length < frameSize) {
    const energy = calculateRms(samples);
    return {
      hasSpeech: energy >= energyThreshold,
      speechFrameCount: energy >= energyThreshold ? 1 : 0,
      totalFrames: 1,
      speechRatio: energy >= energyThreshold ? 1 : 0,
    };
  }

  const totalFrames = Math.floor(samples.length / frameSize);
  let speechFrameCount = 0;

  for (let i = 0; i < totalFrames; i++) {
    const frame = samples.subarray(i * frameSize, (i + 1) * frameSize);
    const vad = evaluateFrameVad(frame, energyThreshold);
    if (vad.isSpeech) {
      speechFrameCount++;
    }
  }

  const speechRatio = speechFrameCount / totalFrames;

  return {
    hasSpeech: speechRatio >= minSpeechRatio,
    speechFrameCount,
    totalFrames,
    speechRatio,
  };
}
