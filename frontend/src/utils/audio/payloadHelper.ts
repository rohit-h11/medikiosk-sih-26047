/**
 * MediKiosk Audio Payload Packaging Utilities
 * Prepares preprocessed audio blobs for backend transmission (multipart FormData, Base64, or ArrayBuffer).
 */

import { ProcessedAudioResult } from '@/types/audio';

export interface AudioPayloadOptions {
  filename?: string;
  language?: string;
  targetLanguage?: string;
  patientId?: string;
  sessionId?: string;
  extraFields?: Record<string, string>;
}

/**
 * Packs a ProcessedAudioResult into a standard multipart/form-data payload ready for fetch / axios POST.
 */
export function createAudioFormData(
  audioResult: ProcessedAudioResult,
  options: AudioPayloadOptions = {}
): FormData {
  const formData = new FormData();
  const filename = options.filename || `patient_audio_${Date.now()}.wav`;

  // Attach WAV Blob as file
  formData.append('file', audioResult.blob, filename);

  if (options.language) {
    formData.append('language', options.language);
  }
  if (options.targetLanguage) {
    formData.append('target_language', options.targetLanguage);
  }
  if (options.patientId) {
    formData.append('patient_id', options.patientId);
  }
  if (options.sessionId) {
    formData.append('session_id', options.sessionId);
  }

  formData.append('audio_format', 'wav');
  formData.append('sample_rate', String(audioResult.stats.targetSampleRate));
  formData.append('duration_sec', String(audioResult.stats.processedDurationSec.toFixed(2)));

  if (options.extraFields) {
    Object.entries(options.extraFields).forEach(([k, v]) => {
      formData.append(k, v);
    });
  }

  return formData;
}

/**
 * Converts a WAV Blob into a Base64 string if JSON-based websockets or REST payloads are preferred.
 */
export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      // Strip Data-URL prefix (data:audio/wav;base64,) if only raw base64 string is needed
      const base64 = result.includes(',') ? result.split(',')[1] : result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Helper to download the preprocessed audio directly to the user's machine for local audio inspection.
 */
export function downloadAudioBlob(blob: Blob, filename = 'preprocessed_16khz.wav') {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}
