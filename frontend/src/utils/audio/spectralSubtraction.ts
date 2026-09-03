/**
 * MediKiosk Robust Spectral Noise Suppressor
 * Uses Minimum-Statistics Noise Tracking + Decision-Directed Wiener Filter
 * to isolate and erase background fan noise, AC hum, and room noise without distorting speech.
 */

import { FFT } from './fft';

export interface SpectralDenoiseOptions {
  /** FFT frame size (power of 2, default 512 = 32ms at 16kHz) */
  frameSize?: number;
  /** Hop size between successive frames (default 256 = 50% overlap) */
  hopSize?: number;
  /** Suppression strength (0.5 to 1.5, default 1.0) */
  suppressionStrength?: number;
  /** Minimum gain floor for noise floor (default 0.08 = -22dB reduction) */
  minGainFloor?: number;
}

/**
 * Creates a standard Hann window.
 */
function createHannWindow(size: number): Float32Array {
  const window = new Float32Array(size);
  for (let i = 0; i < size; i++) {
    window[i] = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (size - 1)));
  }
  return window;
}

/**
 * Applies robust spectral noise reduction to a 16kHz Float32 PCM audio buffer.
 */
export function spectralSubtractNoise(
  samples: Float32Array,
  options: SpectralDenoiseOptions = {}
): Float32Array {
  const {
    frameSize = 512,
    hopSize = 256,
    suppressionStrength = 1.0,
    minGainFloor = 0.08,
  } = options;

  if (samples.length < frameSize) {
    return new Float32Array(samples);
  }

  const fft = new FFT(frameSize);
  const window = createHannWindow(frameSize);

  const numFrames = Math.floor((samples.length - frameSize) / hopSize) + 1;
  const numBins = frameSize / 2 + 1;

  const realBuffer = new Float32Array(frameSize);
  const imagBuffer = new Float32Array(frameSize);

  // 1. Pass 1: Compute magnitude spectrum and total energy for all frames
  const frameSpectra: Float32Array[] = [];
  const frameEnergies: { index: number; energy: number }[] = [];

  for (let f = 0; f < numFrames; f++) {
    const start = f * hopSize;
    let timeEnergy = 0;
    for (let i = 0; i < frameSize; i++) {
      const s = (samples[start + i] || 0) * window[i];
      realBuffer[i] = s;
      imagBuffer[i] = 0;
      timeEnergy += s * s;
    }

    fft.forward(realBuffer, imagBuffer);

    const spectrum = new Float32Array(numBins);
    for (let k = 0; k < numBins; k++) {
      spectrum[k] = realBuffer[k] * realBuffer[k] + imagBuffer[k] * imagBuffer[k];
    }

    frameSpectra.push(spectrum);
    frameEnergies.push({ index: f, energy: timeEnergy });
  }

  // 2. Estimate Noise Floor using Minimum-Energy Frames (True Ambient Noise Tracking)
  // Sort frames by energy to find the quietest 20% (guaranteed to be fan/ambient noise, not voice)
  frameEnergies.sort((a, b) => a.energy - b.energy);
  const noiseFrameCount = Math.max(2, Math.floor(numFrames * 0.20));

  const noisePower = new Float32Array(numBins);
  for (let i = 0; i < noiseFrameCount; i++) {
    const frameIdx = frameEnergies[i].index;
    const spectrum = frameSpectra[frameIdx];
    for (let k = 0; k < numBins; k++) {
      noisePower[k] += spectrum[k] / noiseFrameCount;
    }
  }

  // Prevent division by zero
  for (let k = 0; k < numBins; k++) {
    if (noisePower[k] < 1e-8) noisePower[k] = 1e-8;
  }

  // 3. Pass 2: Apply Smooth Wiener Gain Filter to each frame
  const output = new Float32Array(samples.length);
  const windowWeightSum = new Float32Array(samples.length);
  const prevCleanPower = new Float32Array(numBins);
  const smoothedGain = new Float32Array(numBins).fill(1.0);
  const alpha = 0.85;

  for (let f = 0; f < numFrames; f++) {
    const start = f * hopSize;

    for (let i = 0; i < frameSize; i++) {
      realBuffer[i] = (samples[start + i] || 0) * window[i];
      imagBuffer[i] = 0;
    }

    fft.forward(realBuffer, imagBuffer);

    for (let k = 0; k < numBins; k++) {
      const r = realBuffer[k];
      const im = imagBuffer[k];
      const currentPower = r * r + im * im;

      // Posterior SNR = Signal Power / Noise Power
      const gamma = currentPower / noisePower[k];

      // Decision-Directed Prior SNR estimation
      const priorSnr =
        alpha * (prevCleanPower[k] / noisePower[k]) + (1 - alpha) * Math.max(0, gamma - 1);

      // Wiener Gain calculation
      let targetGain = priorSnr / (priorSnr + 1);
      targetGain = Math.max(minGainFloor, Math.pow(targetGain, suppressionStrength));

      // Temporal smoothing across frames
      smoothedGain[k] = 0.65 * smoothedGain[k] + 0.35 * targetGain;
      const gain = smoothedGain[k];

      realBuffer[k] *= gain;
      imagBuffer[k] *= gain;

      prevCleanPower[k] = currentPower * gain * gain;

      // Symmetrical conjugate for upper spectrum
      if (k > 0 && k < frameSize / 2) {
        const mirrorIdx = frameSize - k;
        realBuffer[mirrorIdx] = realBuffer[k];
        imagBuffer[mirrorIdx] = -imagBuffer[k];
      }
    }

    imagBuffer[frameSize / 2] = 0;

    // Inverse FFT to get cleaned time-domain wave
    fft.inverse(realBuffer, imagBuffer);

    // Overlap-Add synthesis
    for (let i = 0; i < frameSize; i++) {
      const outIdx = start + i;
      if (outIdx < output.length) {
        output[outIdx] += realBuffer[i] * window[i];
        windowWeightSum[outIdx] += window[i] * window[i];
      }
    }
  }

  // 4. Overlap-Add Normalization
  for (let i = 0; i < output.length; i++) {
    if (windowWeightSum[i] > 1e-4) {
      output[i] /= windowWeightSum[i];
    }
  }

  return output;
}
