/**
 * MediKiosk Web Audio API Graph & Real-time Stream DSP
 * Manages microphone stream capture, DSP filter chain (85Hz High-Pass + Compressor),
 * real-time volume/FFT analysis, and raw PCM buffer accumulation.
 */

import { AudioProcessingConfig } from '@/types/audio';

export interface LiveAudioGraph {
  audioContext: AudioContext;
  mediaStream: MediaStream;
  sourceNode: MediaStreamAudioSourceNode;
  highPassFilter: BiquadFilterNode | null;
  compressor: DynamicsCompressorNode | null;
  analyserNode: AnalyserNode;
  processorNode: ScriptProcessorNode;
  getRawSamples: () => Float32Array;
  getCurrentVolume: () => number;
  getFrequencyData: (dataArray: Uint8Array) => void;
  getTimeDomainData: (dataArray: Uint8Array) => void;
  stop: () => void;
}

/**
 * Creates and connects the Web Audio API real-time DSP graph.
 */
export async function createAudioGraph(
  config: AudioProcessingConfig = {}
): Promise<LiveAudioGraph> {
  const {
    noiseSuppression = true,
    echoCancellation = true,
    autoGainControl = false,
    enableHighPassFilter = true,
    highPassCutoff = 110,
    enableCompression = false,
  } = config;

  // 1. Request microphone stream with voice-optimized browser constraints
  const mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      noiseSuppression: { ideal: noiseSuppression },
      echoCancellation: { ideal: echoCancellation },
      autoGainControl: { ideal: autoGainControl },
      channelCount: { ideal: 1 },
    },
    video: false,
  });

  // 2. Initialize AudioContext
  const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const audioContext = new AudioContextClass();

  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }

  const sourceNode = audioContext.createMediaStreamSource(mediaStream);

  // 3. Node references
  let highPassFilter: BiquadFilterNode | null = null;
  let compressor: DynamicsCompressorNode | null = null;

  let lastNode: AudioNode = sourceNode;

  // 4. Insert 85Hz High-Pass Filter (strips desk thumps, AC hum, wind rumble)
  if (enableHighPassFilter) {
    highPassFilter = audioContext.createBiquadFilter();
    highPassFilter.type = 'highpass';
    highPassFilter.frequency.setValueAtTime(highPassCutoff, audioContext.currentTime);
    highPassFilter.Q.setValueAtTime(0.707, audioContext.currentTime); // Butterworth Q
    lastNode.connect(highPassFilter);
    lastNode = highPassFilter;
  }

  // 5. Insert Dynamics Compressor (smooths loud speech bursts & sudden clicks)
  if (enableCompression) {
    compressor = audioContext.createDynamicsCompressor();
    compressor.threshold.setValueAtTime(-24, audioContext.currentTime);
    compressor.knee.setValueAtTime(12, audioContext.currentTime);
    compressor.ratio.setValueAtTime(4, audioContext.currentTime);
    compressor.attack.setValueAtTime(0.003, audioContext.currentTime);
    compressor.release.setValueAtTime(0.25, audioContext.currentTime);
    lastNode.connect(compressor);
    lastNode = compressor;
  }

  // 6. Insert AnalyserNode for real-time volume & visualizer telemetry
  const analyserNode = audioContext.createAnalyser();
  analyserNode.fftSize = 512;
  analyserNode.smoothingTimeConstant = 0.8;
  lastNode.connect(analyserNode);

  // 7. Buffer collector using ScriptProcessor (bufferSize 4096 = ~85ms at 48kHz)
  const bufferSize = 4096;
  const processorNode = audioContext.createScriptProcessor(bufferSize, 1, 1);
  const recordedChunks: Float32Array[] = [];
  let totalLength = 0;

  processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
    const inputData = e.inputBuffer.getChannelData(0);
    // Clone channel data
    const chunk = new Float32Array(inputData);
    recordedChunks.push(chunk);
    totalLength += chunk.length;
  };

  analyserNode.connect(processorNode);
  // Route to dummy destination to keep ScriptProcessor running (silent)
  processorNode.connect(audioContext.destination);

  // 8. Methods to extract telemetry and final buffer
  const getRawSamples = (): Float32Array => {
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of recordedChunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    return merged;
  };

  const timeData = new Uint8Array(analyserNode.fftSize);
  const getCurrentVolume = (): number => {
    analyserNode.getByteTimeDomainData(timeData);
    let sum = 0;
    for (let i = 0; i < timeData.length; i++) {
      const normalized = (timeData[i] - 128) / 128;
      sum += normalized * normalized;
    }
    const rms = Math.sqrt(sum / timeData.length);
    return Math.min(1.0, rms * 3.5); // Scaled for intuitive UI meter (0.0 to 1.0)
  };

  const getFrequencyData = (dataArray: Uint8Array): void => {
    analyserNode.getByteFrequencyData(dataArray as any);
  };

  const getTimeDomainData = (dataArray: Uint8Array): void => {
    analyserNode.getByteTimeDomainData(dataArray as any);
  };

  const stop = (): void => {
    try {
      processorNode.disconnect();
      analyserNode.disconnect();
      if (compressor) compressor.disconnect();
      if (highPassFilter) highPassFilter.disconnect();
      sourceNode.disconnect();

      // Stop all microphone tracks to release hardware light
      mediaStream.getTracks().forEach((track) => track.stop());

      if (audioContext.state !== 'closed') {
        audioContext.close();
      }
    } catch (err) {
      console.warn('AudioGraph teardown warning:', err);
    }
  };

  return {
    audioContext,
    mediaStream,
    sourceNode,
    highPassFilter,
    compressor,
    analyserNode,
    processorNode,
    getRawSamples,
    getCurrentVolume,
    getFrequencyData,
    getTimeDomainData,
    stop,
  };
}
