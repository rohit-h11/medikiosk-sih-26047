/**
 * MediKiosk Push-To-Talk Diagnostic & Testing Component
 * A functional harness to test Push-to-Talk recording, Web Audio DSP preprocessing,
 * live volume meter, VAD detection, and WAV payload generation.
 */

import React, { useState, useRef } from 'react';
import { usePushToTalk } from '@/hooks/usePushToTalk';
import { useAudioVisualizer } from '@/hooks/useAudioVisualizer';
import { useVoiceContext } from '@/context/VoiceContext';
import { createAudioFormData, downloadAudioBlob } from '@/utils/audio/payloadHelper';
import { ProcessedAudioResult } from '@/types/audio';

export const PushToTalkTester: React.FC = () => {
  const { language, setLanguage, supportedLanguages } = useVoiceContext();
  const [outputLogs, setOutputLogs] = useState<string[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const addLog = (msg: string) => {
    setOutputLogs((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 19)]);
  };

  const {
    state,
    isRecording,
    isProcessing,
    volumeLevel,
    duration,
    error,
    lastResult,
    stats,
    audioBlob,
    previewUrl,
    startRecording,
    stopRecording,
    cancelRecording,
    toggleRecording,
    bindPushToTalk,
    audioGraph,
  } = usePushToTalk({
    onStateChange: (newState) => addLog(`State changed: ${newState}`),
    onError: (err) => addLog(`Error: ${err.message}`),
    onAudioReady: (result: ProcessedAudioResult) => {
      addLog(
        `Audio Preprocessed: ${result.stats.processedDurationSec.toFixed(2)}s (Trimmed ${result.stats.silenceTrimmedSec.toFixed(2)}s silence) | ${result.stats.byteLength} bytes | Speech detected: ${result.stats.hasSpeech}`
      );
      // Example of packing into FormData ready for backend
      const formData = createAudioFormData(result, { language });
      addLog(`Prepared FormData with file key (${result.stats.targetSampleRate}Hz Mono WAV)`);
    },
  });

  // Attach live visualizer to canvas
  useAudioVisualizer({
    canvasRef,
    analyserNode: audioGraph?.analyserNode ?? null,
    mode: 'bars',
    primaryColor: '#2563eb',
    secondaryColor: '#60a5fa',
  });

  const pttBindings = bindPushToTalk();

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: '750px', margin: '20px auto', padding: '24px', border: '1px solid #e2e8f0', borderRadius: '12px', background: '#ffffff', color: '#1e293b' }}>
      <h2 style={{ margin: '0 0 8px 0', fontSize: '1.5rem', fontWeight: 600 }}>
        🎙️ Push-to-Talk & Audio Preprocessing Tester
      </h2>
      <p style={{ margin: '0 0 20px 0', color: '#64748b', fontSize: '0.9rem' }}>
        Press and hold the button below (or hold Spacebar) to talk. Audio will be captured, passed through an 85Hz High-Pass filter & compressor, downsampled to 16kHz mono, trimmed of silence, normalized to -1dB, and encoded into a standard 16-bit WAV.
      </p>

      {/* Language Selector */}
      <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>Patient Language:</label>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.9rem' }}
        >
          {supportedLanguages.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.nativeName} ({lang.name} - {lang.code})
            </option>
          ))}
        </select>
      </div>

      {/* Status Bar */}
      <div style={{ display: 'flex', gap: '16px', padding: '12px', background: '#f8fafc', borderRadius: '8px', marginBottom: '20px', fontSize: '0.85rem' }}>
        <div><strong>Status:</strong> <span style={{ color: isRecording ? '#dc2626' : '#2563eb', fontWeight: 600 }}>{state.toUpperCase()}</span></div>
        <div><strong>Duration:</strong> {duration.toFixed(2)}s</div>
        <div><strong>Speech Detected:</strong> {stats ? (stats.hasSpeech ? '✅ Yes' : '❌ No') : '-'}</div>
      </div>

      {/* Real-time Volume Bar */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b', marginBottom: '4px' }}>
          <span>Input Volume</span>
          <span>{Math.round(volumeLevel * 100)}%</span>
        </div>
        <div style={{ height: '10px', background: '#e2e8f0', borderRadius: '5px', overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${Math.min(100, Math.round(volumeLevel * 100))}%`,
              background: isRecording ? (volumeLevel > 0.8 ? '#ef4444' : '#10b981') : '#94a3b8',
              transition: 'width 0.05s ease-out',
            }}
          />
        </div>
      </div>

      {/* Live FFT Canvas Visualizer */}
      <div style={{ marginBottom: '20px', textAlign: 'center', background: '#0f172a', borderRadius: '8px', padding: '12px' }}>
        <canvas ref={canvasRef} width={600} height={100} style={{ width: '100%', height: '100px', display: 'block' }} />
      </div>

      {/* Push-to-Talk Interactive Controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center', marginBottom: '24px' }}>
        {/* Main Hold-to-Talk Button */}
        <button
          {...pttBindings}
          style={{
            flex: '1 1 200px',
            padding: '16px 24px',
            fontSize: '1rem',
            fontWeight: 600,
            color: '#ffffff',
            background: isRecording ? '#dc2626' : '#2563eb',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            userSelect: 'none',
            boxShadow: isRecording ? '0 0 15px rgba(220, 38, 38, 0.5)' : 'none',
            transition: 'all 0.15s ease',
          }}
        >
          {isRecording ? '🔴 Release to Stop & Preprocess' : isProcessing ? '⚙️ Preprocessing Audio...' : '🎙️ Hold to Talk (or Spacebar)'}
        </button>

        {/* Toggle Mode Button (Accessibility) */}
        <button
          onClick={toggleRecording}
          style={{
            padding: '16px 20px',
            fontSize: '0.9rem',
            fontWeight: 500,
            background: '#f1f5f9',
            border: '1px solid #cbd5e1',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          {isRecording ? '⏹️ Click Stop' : '▶️ Click Toggle'}
        </button>

        {/* Cancel Button */}
        {isRecording && (
          <button
            onClick={cancelRecording}
            style={{
              padding: '16px 20px',
              fontSize: '0.9rem',
              fontWeight: 500,
              background: '#fee2e2',
              color: '#991b1b',
              border: '1px solid #fca5a5',
              borderRadius: '8px',
              cursor: 'pointer',
            }}
          >
            ❌ Cancel
          </button>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div style={{ padding: '12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#991b1b', marginBottom: '20px', fontSize: '0.85rem' }}>
          <strong>Error:</strong> {error.message}
        </div>
      )}

      {/* Preprocessed Audio Result & Telemetry */}
      {lastResult && stats && (
        <div style={{ padding: '16px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', marginBottom: '20px' }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '1.05rem', color: '#166534' }}>
            ✨ Preprocessed 16kHz Audio Ready
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px', fontSize: '0.82rem', marginBottom: '14px', color: '#14532d' }}>
            <div><strong>Original Sample Rate:</strong> {stats.originalSampleRate} Hz</div>
            <div><strong>Target Sample Rate:</strong> {stats.targetSampleRate} Hz (Mono)</div>
            <div><strong>Original Duration:</strong> {stats.originalDurationSec.toFixed(2)}s</div>
            <div><strong>Final Duration:</strong> {stats.processedDurationSec.toFixed(2)}s</div>
            <div><strong>Silence Trimmed:</strong> {stats.silenceTrimmedSec.toFixed(2)}s</div>
            <div><strong>Peak Level:</strong> {stats.peakDbfs.toFixed(1)} dBFS</div>
            <div><strong>Payload Size:</strong> {(stats.byteLength / 1024).toFixed(1)} KB</div>
            <div><strong>Speech Detected:</strong> {stats.hasSpeech ? 'Yes (VAD Passed)' : 'No (Silence/Low Energy)'}</div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {previewUrl && (
              <audio controls src={previewUrl} style={{ height: '36px', flex: '1 1 250px' }} />
            )}
            {audioBlob && (
              <button
                onClick={() => downloadAudioBlob(audioBlob, `patient_${language}_16khz.wav`)}
                style={{
                  padding: '8px 14px',
                  background: '#166534',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                💾 Download 16kHz WAV
              </button>
            )}
          </div>
        </div>
      )}

      {/* Activity Logs */}
      <div>
        <h4 style={{ margin: '0 0 6px 0', fontSize: '0.85rem', color: '#64748b' }}>Console Event Log:</h4>
        <div style={{ background: '#0f172a', color: '#38bdf8', padding: '10px 14px', borderRadius: '6px', fontSize: '0.75rem', fontFamily: 'monospace', maxHeight: '140px', overflowY: 'auto' }}>
          {outputLogs.length === 0 ? (
            <span style={{ color: '#64748b' }}>Waiting for push-to-talk interaction...</span>
          ) : (
            outputLogs.map((log, index) => <div key={index}>{log}</div>)
          )}
        </div>
      </div>
    </div>
  );
};
