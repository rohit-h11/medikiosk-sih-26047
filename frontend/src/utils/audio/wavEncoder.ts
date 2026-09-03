/**
 * Pure JavaScript 16-bit Linear PCM WAV Audio Encoder
 * Encodes Float32 PCM samples into a standard RIFF/WAVE audio container (.wav Blob)
 */

export function encodeWAV(
  samples: Float32Array,
  sampleRate: number = 16000,
  numChannels: number = 1,
  bitDepth: number = 16
): Blob {
  const bytesPerSample = bitDepth / 8;
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples.length * bytesPerSample;
  const bufferSize = 44 + dataSize; // 44 bytes header + raw PCM payload

  const buffer = new ArrayBuffer(bufferSize);
  const view = new DataView(buffer);

  // 1. RIFF chunk descriptor
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true); // File size - 8
  writeString(view, 8, 'WAVE');

  // 2. "fmt " sub-chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size for PCM format
  view.setUint16(20, 1, true); // AudioFormat: 1 = Linear PCM
  view.setUint16(22, numChannels, true); // NumChannels (1 = Mono)
  view.setUint32(24, sampleRate, true); // SampleRate (e.g. 16000)
  view.setUint32(28, byteRate, true); // ByteRate = SampleRate * NumChannels * BitsPerSample/8
  view.setUint16(32, blockAlign, true); // BlockAlign = NumChannels * BitsPerSample/8
  view.setUint16(34, bitDepth, true); // BitsPerSample (16-bit)

  // 3. "data" sub-chunk
  writeString(view, 36, 'data');
  view.setUint32(40, dataSize, true); // Subchunk2Size

  // 4. Write 16-bit PCM samples with saturation clipping protection
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    // Clamp sample to [-1.0, 1.0] range
    const s = Math.max(-1, Math.min(1, samples[i]));
    // Convert float to 16-bit signed integer [-32768, 32767]
    const intSample = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, intSample, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}

/**
 * Helper to write ASCII strings to DataView at specified byte offset
 */
function writeString(view: DataView, offset: number, string: string): void {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}
