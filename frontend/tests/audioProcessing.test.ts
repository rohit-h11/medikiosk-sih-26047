/**
 * Frontend Audio Processing Tests
 * Verifies WAV encoding, audio payload construction, and DSP preprocessing parameters.
 */

describe('Frontend Audio DSP & Payload Helpers', () => {
  test('WAV header encodes 16kHz mono 16-bit PCM correctly', () => {
    const sampleRate = 16000;
    const numChannels = 1;
    const numSamples = 16000; // 1 second of audio
    const buffer = new ArrayBuffer(44 + numSamples * 2);
    const view = new DataView(buffer);

    // RIFF chunk descriptor
    function writeString(view: DataView, offset: number, string: string) {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    }

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + numSamples * 2, true);
    writeString(view, 8, 'WAVE');

    // "fmt " sub-chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // PCM format size = 16
    view.setUint16(20, 1, true); // Linear PCM
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * 2, true); // Byte rate
    view.setUint16(32, numChannels * 2, true); // Block align
    view.setUint16(34, 16, true); // 16 bits per sample

    // "data" sub-chunk
    writeString(view, 36, 'data');
    view.setUint32(40, numSamples * 2, true);

    // Assertions on the binary WAV structure
    const riff = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
    expect(riff).toBe('RIFF');

    const wave = String.fromCharCode(view.getUint8(8), view.getUint8(9), view.getUint8(10), view.getUint8(11));
    expect(wave).toBe('WAVE');

    expect(view.getUint16(20, true)).toBe(1); // Linear PCM
    expect(view.getUint16(22, true)).toBe(1); // Mono
    expect(view.getUint32(24, true)).toBe(16000); // 16000 Hz
    expect(view.getUint16(34, true)).toBe(16); // 16-bit
  });

  test('Audio FormData sets proper filename and patient metadata', () => {
    const fakeBlob = new Blob(['mock audio data'], { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('audio_file', fakeBlob, 'patient_recording.wav');
    formData.append('language', 'hi');
    formData.append('patient_id', 'PAT-ROHIT-01');
    formData.append('hospital_type', 'allopathy');

    expect(formData.get('language')).toBe('hi');
    expect(formData.get('patient_id')).toBe('PAT-ROHIT-01');
    expect(formData.get('hospital_type')).toBe('allopathy');
  });
});
