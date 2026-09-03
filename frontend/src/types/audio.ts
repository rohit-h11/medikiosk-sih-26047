/**
 * MediKiosk Audio & Push-To-Talk Type Definitions
 */

export type PushToTalkState =
  | 'idle'
  | 'preparing'
  | 'recording'
  | 'processing'
  | 'completed'
  | 'error';

export interface AudioProcessingConfig {
  /** Target sample rate for ASR (default 16000 Hz for Whisper / Bhashini / Sarvam) */
  targetSampleRate?: number;
  /** Whether to enable browser native noise suppression (default true) */
  noiseSuppression?: boolean;
  /** Whether to enable browser echo cancellation (default true) */
  echoCancellation?: boolean;
  /** Whether to enable browser auto gain control (default true) */
  autoGainControl?: boolean;
  /** Enable High-Pass filter to strip low-frequency rumble & AC hum (default true) */
  enableHighPassFilter?: boolean;
  /** High-pass cutoff frequency in Hz (default 105 Hz: natural voice preservation + fan cut) */
  highPassCutoff?: number;
  /** Enable dynamic range compression to prevent clipping from loud speech (default true) */
  enableCompression?: boolean;
  /** Enable smooth Decision-Directed Wiener spectral noise suppression (default true) */
  enableSpectralDenoise?: boolean;
  /** Noise suppression strength (0.0 to 1.0, default 0.75) */
  spectralDenoiseStrength?: number;
  /** Enable adaptive downward noise gate (default false to avoid clipping speech) */
  enableNoiseGate?: boolean;
  /** RMS threshold for noise gate if enabled (default 0.007) */
  noiseGateThreshold?: number;
  /** Trim leading and trailing silence from the recorded audio (default true) */
  trimSilence?: boolean;
  /** RMS threshold below which audio is considered silence (default 0.007) */
  silenceRmsThreshold?: number;
  /** Padding in seconds to keep before and after detected speech (default 0.20s) */
  silencePaddingSec?: number;
  /** Normalize peak amplitude to target dBFS (default true) */
  normalizePeak?: boolean;
  /** Target peak amplitude in linear scale (default 0.90 = ~-0.9 dBFS) */
  targetPeak?: number;
  /** Minimum recording duration in ms; records shorter than this are rejected (default 350ms) */
  minDurationMs?: number;
  /** Maximum recording safety duration in ms before auto-stopping (default 30000ms = 30s) */
  maxDurationMs?: number;
}

export interface AudioPreprocessingStats {
  /** Original sample rate from patient microphone (e.g., 44100 or 48000 Hz) */
  originalSampleRate: number;
  /** Target sample rate after resampling (typically 16000 Hz) */
  targetSampleRate: number;
  /** Duration in seconds before silence trimming */
  originalDurationSec: number;
  /** Final duration in seconds after trimming */
  processedDurationSec: number;
  /** Total seconds of silence stripped */
  silenceTrimmedSec: number;
  /** Signal Peak amplitude in linear (0.0 to 1.0) */
  peakAmplitude: number;
  /** Peak in dBFS (decibels relative to full scale) */
  peakDbfs: number;
  /** Root-mean-square energy of the signal */
  rmsEnergy: number;
  /** Size of the final WAV payload in bytes */
  byteLength: number;
  /** Whether meaningful speech was detected by Voice Activity Detection */
  hasSpeech: boolean;
}

export interface ProcessedAudioResult {
  /** Standard 16-bit PCM Mono WAV Blob (MIME: audio/wav) */
  blob: Blob;
  /** Float32Array PCM samples at target sample rate */
  pcmSamples: Float32Array;
  /** Detailed audio DSP statistics */
  stats: AudioPreprocessingStats;
  /** URL created via URL.createObjectURL for immediate playback/preview */
  previewUrl: string;
}

export interface VadResult {
  /** Whether the audio frame or buffer contains voice activity */
  isSpeech: boolean;
  /** Computed energy / RMS of the analysed frame */
  energy: number;
  /** Spectral centroid or high frequency ratio */
  spectralCentroid?: number;
}

export interface PushToTalkBindings {
  onMouseDown: (e: React.MouseEvent) => void;
  onMouseUp: (e: React.MouseEvent) => void;
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
  onTouchCancel: (e: React.TouchEvent) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onKeyUp: (e: React.KeyboardEvent) => void;
}

export interface UsePushToTalkOptions {
  /** Optional audio processing configuration overrides */
  config?: AudioProcessingConfig;
  /** Callback fired as soon as audio has been captured, preprocessed, and encoded */
  onAudioReady?: (result: ProcessedAudioResult) => void | Promise<void>;
  /** Callback fired on state transitions */
  onStateChange?: (state: PushToTalkState) => void;
  /** Callback fired if an error occurs (e.g. microphone permission denied) */
  onError?: (error: Error) => void;
  /** Callback for real-time volume changes (0.0 to 1.0) */
  onVolumeChange?: (volume: number) => void;
}
