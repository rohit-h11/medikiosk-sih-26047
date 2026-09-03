/**
 * MediKiosk Adaptive Downward Expander & Noise Gate
 * Smoothly mutes background fan noise during pauses and gaps between words.
 */

import { calculateRms } from './vad';

export interface NoiseGateOptions {
  /** RMS threshold below which gating begins (default 0.018) */
  threshold?: number;
  /** Minimum gain multiplier during silence (0.0 = total mute, 0.02 = -34dB, default 0.02) */
  floorGain?: number;
  /** Attack time in seconds: how fast the gate opens when speech begins (default 0.005 = 5ms) */
  attackSec?: number;
  /** Release time in seconds: how smoothly the gate closes when speech stops (default 0.060 = 60ms) */
  releaseSec?: number;
  /** Frame size for energy analysis in samples (default 160 = 10ms at 16kHz) */
  frameSize?: number;
}

/**
 * Applies a smooth downward expander / noise gate to a 16kHz Float32 PCM buffer.
 */
export function applyNoiseGate(
  samples: Float32Array,
  sampleRate: number = 16000,
  options: NoiseGateOptions = {}
): Float32Array {
  const {
    threshold = 0.018,
    floorGain = 0.02,
    attackSec = 0.005,
    releaseSec = 0.060,
    frameSize = 160, // 10ms at 16kHz
  } = options;

  if (samples.length === 0) return samples;

  const result = new Float32Array(samples.length);
  const numFrames = Math.floor(samples.length / frameSize);

  // Attack and release smoothing coefficients
  const attackCoeff = Math.exp(-1.0 / (attackSec * sampleRate));
  const releaseCoeff = Math.exp(-1.0 / (releaseSec * sampleRate));

  let currentGain = floorGain;

  for (let f = 0; f < numFrames; f++) {
    const start = f * frameSize;
    const end = Math.min(start + frameSize, samples.length);
    const frame = samples.subarray(start, end);
    const rms = calculateRms(frame);

    // Target gain: 1.0 (open) if voice energy > threshold, floorGain (muted) if quiet fan
    const targetGain = rms >= threshold ? 1.0 : floorGain;

    // Apply sample-by-sample smooth exponential crossfade
    for (let i = start; i < end; i++) {
      if (targetGain > currentGain) {
        // Opening gate (Attack)
        currentGain = targetGain + (currentGain - targetGain) * attackCoeff;
      } else {
        // Closing gate (Release)
        currentGain = targetGain + (currentGain - targetGain) * releaseCoeff;
      }

      result[i] = samples[i] * currentGain;
    }
  }

  // Handle any remaining trailing samples
  const remainingStart = numFrames * frameSize;
  for (let i = remainingStart; i < samples.length; i++) {
    result[i] = samples[i] * currentGain;
  }

  return result;
}
