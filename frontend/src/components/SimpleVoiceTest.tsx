import React, { useState, useRef } from 'react';
import { usePushToTalk } from '../hooks/usePushToTalk';
import { ProcessedAudioResult } from '../types/audio';

interface ChatMessage {
  role: 'assistant' | 'patient';
  contentNative: string;
  contentEnglish?: string;
  audioBase64?: string;
}

interface TouchOption {
  id: string;
  label: string;
  label_native?: string;
  value: string;
  slot_tag?: string;
}

export const SimpleVoiceTest: React.FC = () => {
  const [language, setLanguage] = useState<string>('hi');
  const [patientId, setPatientId] = useState<string>(() => `PAT-DEMO-${Math.floor(1000 + Math.random() * 9000)}`);
  const [sessionId, setSessionId] = useState<string>(() => `sess_${Math.random().toString(36).substring(2, 10)}`);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      contentNative: 'नमस्ते! मेडीकियोस्क में आपका स्वागत है। आज आपको क्या परेशानी या तकलीफ हो रही है?',
      contentEnglish: 'Hello! Welcome to MediKiosk. What health symptoms or discomfort are you experiencing today?',
    },
  ]);
  const [touchOptions, setTouchOptions] = useState<TouchOption[]>([
    { id: 'opt_fever', label: 'Fever & Cough', label_native: 'बुखार और खांसी', value: 'मुझे बुखार और खांसी है' },
    { id: 'opt_stomach', label: 'Stomach Pain', label_native: 'पेट में दर्द', value: 'मुझे पेट में तेज दर्द है' },
    { id: 'opt_chest', label: 'Chest Discomfort', label_native: 'सीने में तकलीफ', value: 'मुझे सीने में दर्द या भारीपन है' },
    { id: 'opt_headache', label: 'Severe Headache', label_native: 'तेज सिरदर्द', value: 'मुझे बहुत तेज सिरदर्द है' },
  ]);
  const [isAiSpeaking, setIsAiSpeaking] = useState<boolean>(false);
  const [isCallingBackend, setIsCallingBackend] = useState<boolean>(false);
  const [typedInput, setTypedInput] = useState<string>('');
  const [socratesSlots, setSocratesSlots] = useState<string[]>([]);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [clinicalSummary, setClinicalSummary] = useState<string | null>(null);

  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  // Helper to play synthesized voice audio
  const playAudioBase64 = (base64Data?: string) => {
    if (!base64Data) return;
    try {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      const audio = new Audio(`data:audio/wav;base64,${base64Data}`);
      audioPlayerRef.current = audio;
      setIsAiSpeaking(true);
      audio.onended = () => setIsAiSpeaking(false);
      audio.onerror = () => setIsAiSpeaking(false);
      audio.play().catch(() => setIsAiSpeaking(false));
    } catch (e) {
      console.error('Audio playback failed', e);
      setIsAiSpeaking(false);
    }
  };

  // Sends the turn payload to the backend FastAPI endpoint
  const sendTurnToBackend = async (audioBlob?: Blob, textInput?: string, optionId?: string) => {
    setIsCallingBackend(true);

    try {
      const formData = new FormData();
      if (audioBlob) {
        formData.append('audio_file', audioBlob, 'patient_recording.wav');
      }
      if (textInput) {
        formData.append('text_response', textInput);
      }
      if (optionId) {
        formData.append('selected_option_id', optionId);
      }
      formData.append('session_id', sessionId);
      formData.append('patient_id', patientId);
      formData.append('language', language);
      formData.append('max_turns', '10');

      // Convert local message history into JSON for the backend
      const historyPayload = messages.map((m) => ({
        role: m.role,
        content: m.contentEnglish || m.contentNative,
      }));
      formData.append('conversation_history', JSON.stringify(historyPayload));

      const res = await fetch('http://localhost:8000/api/v1/interview/turn', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();

      // 1. Add patient message to transcript
      const patientMsg: ChatMessage = {
        role: 'patient',
        contentNative: data.patient_utterance?.native || textInput || 'Voice response',
        contentEnglish: data.patient_utterance?.english,
      };

      const updatedMessages = [...messages, patientMsg];

      // 2. Add AI response message if question present OR closing message upon completion
      if (data.next_question) {
        const aiMsg: ChatMessage = {
          role: 'assistant',
          contentNative: data.next_question.native,
          contentEnglish: data.next_question.english,
          audioBase64: data.audio_response?.audio_base64,
        };
        updatedMessages.push(aiMsg);
        playAudioBase64(data.audio_response?.audio_base64);
      } else if (data.is_completed && data.closing_message) {
        const closingMsg: ChatMessage = {
          role: 'assistant',
          contentNative: data.closing_message.native || data.closing_message.english,
          contentEnglish: data.closing_message.english,
          audioBase64: data.audio_response?.audio_base64,
        };
        updatedMessages.push(closingMsg);
        playAudioBase64(data.audio_response?.audio_base64);
      }

      setMessages(updatedMessages);
      setTouchOptions(data.touch_options || []);
      setSocratesSlots(data.covered_slots || []);

      if (data.is_completed) {
        setIsCompleted(true);
        setClinicalSummary(data.clinical_summary || (typeof data.closing_message === 'string' ? data.closing_message : data.closing_message?.english) || 'Interview completed.');
      }
    } catch (err) {
      console.error('Turn submission error:', err);
      alert('Could not connect to backend at http://localhost:8000. Ensure FastAPI backend is running!');
    } finally {
      setIsCallingBackend(false);
    }
  };

  // Callback when Push-to-Talk finishes recording & cleaning audio
  const handleAudioReady = (result: ProcessedAudioResult) => {
    sendTurnToBackend(result.blob);
  };

  // Push-to-talk hook with our clean 110Hz HPF + Wiener Filter pipeline
  const { isRecording, isProcessing, volumeLevel, duration, bindPushToTalk } = usePushToTalk({
    onAudioReady: handleAudioReady,
    config: {
      enableSpectralDenoise: true,
      enableHighPassFilter: true,
    },
  });

  const handleTouchOptionClick = (option: TouchOption) => {
    sendTurnToBackend(undefined, option.value, option.id);
  };

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedInput.trim()) return;
    sendTurnToBackend(undefined, typedInput.trim());
    setTypedInput('');
  };

  const handleResetSession = () => {
    setPatientId(`PAT-DEMO-${Math.floor(1000 + Math.random() * 9000)}`);
    setSessionId(`sess_${Math.random().toString(36).substring(2, 10)}`);
    setMessages([
      {
        role: 'assistant',
        contentNative: 'नमस्ते! मेडीकियोस्क में आपका स्वागत है। आज आपको क्या परेशानी हो रही है?',
        contentEnglish: 'Hello! Welcome to MediKiosk. What symptoms are you experiencing today?',
      },
    ]);
    setTouchOptions([
      { id: 'opt_fever', label: 'Fever & Cough', label_native: 'बुखार और खांसी', value: 'मुझे बुखार और खांसी है' },
      { id: 'opt_stomach', label: 'Stomach Pain', label_native: 'पेट में दर्द', value: 'मुझे पेट में तेज दर्द है' },
      { id: 'opt_chest', label: 'Chest Discomfort', label_native: 'सीने में तकलीफ', value: 'मुझे सीने में दर्द है' },
      { id: 'opt_headache', label: 'Severe Headache', label_native: 'तेज सिरदर्द', value: 'मुझे सिरदर्द है' },
    ]);
    setSocratesSlots([]);
    setIsCompleted(false);
    setClinicalSummary(null);
  };

  return (
    <div style={{ maxWidth: '640px', margin: '30px auto', padding: '24px', fontFamily: 'system-ui, -apple-system, sans-serif', background: '#ffffff', borderRadius: '20px', boxShadow: '0 8px 32px rgba(0,0,0,0.08)' }}>
      
      {/* Top Header & Language Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #f1f5f9', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.3rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '8px' }}>
            🏥 MediKiosk AI Doctor
          </h2>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '2px' }}>
            Patient: <strong style={{ color: '#2563eb' }}>{patientId}</strong> | Session: <span style={{ fontFamily: 'monospace' }}>{sessionId}</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.85rem', fontWeight: 600, background: '#f8fafc', color: '#0f172a', outline: 'none' }}
          >
            <option value="hi">🇮🇳 Hindi (हिंदी)</option>
            <option value="ta">🇮🇳 Tamil (தமிழ்)</option>
            <option value="te">🇮🇳 Telugu (తెలుగు)</option>
            <option value="mr">🇮🇳 Marathi (मराठी)</option>
            <option value="bn">🇮🇳 Bengali (বাংলা)</option>
            <option value="en">🌐 English</option>
          </select>

          <button
            onClick={handleResetSession}
            title="Start fresh intake for a new patient"
            style={{ padding: '6px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', background: '#f1f5f9', fontSize: '0.8rem', cursor: 'pointer', color: '#0f172a', fontWeight: 600 }}
          >
            🆕 New Patient
          </button>
        </div>
      </div>

      {/* SOCRATES Covered Slots Progress Bar */}
      {socratesSlots.length > 0 && (
        <div style={{ marginBottom: '16px', padding: '10px 14px', background: '#f0fdf4', borderRadius: '10px', border: '1px solid #bbf7d0', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#166534' }}>SOCRATES Covered:</span>
          {socratesSlots.map((slot) => (
            <span key={slot} style={{ fontSize: '0.75rem', background: '#dcfce7', color: '#15803d', padding: '2px 8px', borderRadius: '12px', fontWeight: 600, textTransform: 'capitalize' }}>
              ✓ {slot}
            </span>
          ))}
        </div>
      )}

      {/* Conversation Transcript Stream */}
      <div style={{ height: '240px', overflowY: 'auto', padding: '12px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
        {messages.map((msg, index) => {
          const isAi = msg.role === 'assistant';
          return (
            <div
              key={index}
              style={{
                alignSelf: isAi ? 'flex-start' : 'flex-end',
                maxWidth: '85%',
                padding: '12px 16px',
                borderRadius: isAi ? '16px 16px 16px 4px' : '16px 16px 4px 16px',
                background: isAi ? '#ffffff' : '#3b82f6',
                color: isAi ? '#0f172a' : '#ffffff',
                boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                border: isAi ? '1px solid #e2e8f0' : 'none',
              }}
            >
              <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: '4px', opacity: 0.8 }}>
                {isAi ? '🤖 MediKiosk AI Doctor' : '👤 You (Patient)'}
              </div>
              <div style={{ fontSize: '0.95rem', lineHeight: 1.4, fontWeight: 500 }}>
                {msg.contentNative}
              </div>
              {msg.contentEnglish && msg.contentEnglish !== msg.contentNative && (
                <div style={{ fontSize: '0.8rem', color: isAi ? '#64748b' : '#dbeafe', marginTop: '4px', fontStyle: 'italic' }}>
                  Subtitle: "{msg.contentEnglish}"
                </div>
              )}
            </div>
          );
        })}

        {isCallingBackend && (
          <div style={{ alignSelf: 'flex-start', padding: '8px 14px', background: '#e0f2fe', borderRadius: '12px', color: '#0369a1', fontSize: '0.85rem', fontWeight: 600 }}>
            ⏳ Thinking & Synthesizing Voice...
          </div>
        )}
      </div>

      {/* Completed Summary Card */}
      {isCompleted && (
        <div style={{ marginBottom: '20px', padding: '16px', background: '#eff6ff', borderRadius: '12px', border: '1px solid #bfdbfe', textAlign: 'left' }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#1e40af', fontSize: '0.95rem' }}>📋 Clinical Summary for Doctor:</h4>
          <div style={{ margin: 0, fontSize: '0.85rem', color: '#1e3a8a', lineHeight: 1.5, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{clinicalSummary}</div>
        </div>
      )}

      {/* Dynamic Touchscreen Options Generated by LLM */}
      {!isCompleted && touchOptions.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600, marginBottom: '8px', textAlign: 'left' }}>
            👇 Tap an answer or speak below:
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
            {touchOptions.map((opt) => (
              <button
                key={opt.id}
                onClick={() => handleTouchOptionClick(opt)}
                disabled={isCallingBackend || isRecording}
                style={{
                  padding: '10px 12px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  background: '#f8fafc',
                  color: '#0f172a',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: isCallingBackend ? 'not-allowed' : 'pointer',
                  textAlign: 'center',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#e2e8f0')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#f8fafc')}
              >
                <div>{opt.label_native || opt.label}</div>
                {opt.label_native && opt.label_native !== opt.label && (
                  <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 400 }}>{opt.label}</div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Push-to-Talk Main Button */}
      {!isCompleted && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', margin: '20px 0' }}>
          <button
            {...bindPushToTalk()}
            disabled={isCallingBackend}
            style={{
              width: '130px',
              height: '130px',
              borderRadius: '50%',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 700,
              color: '#ffffff',
              background: isRecording ? '#ef4444' : isCallingBackend ? '#94a3b8' : isAiSpeaking ? '#8b5cf6' : '#3b82f6',
              cursor: isCallingBackend ? 'not-allowed' : 'pointer',
              outline: 'none',
              userSelect: 'none',
              transform: isRecording ? `scale(${1 + volumeLevel * 0.25})` : 'scale(1)',
              boxShadow: isRecording
                ? `0 0 ${20 + volumeLevel * 40}px rgba(239, 68, 68, 0.6)`
                : isAiSpeaking
                ? '0 0 24px rgba(139, 92, 246, 0.5)'
                : '0 4px 14px rgba(59, 130, 246, 0.35)',
              transition: 'transform 0.05s ease, background 0.2s ease',
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <span style={{ fontSize: '2.2rem' }}>
              {isRecording ? '🔴' : isCallingBackend ? '⏳' : isAiSpeaking ? '🔊' : '🎤'}
            </span>
            <span style={{ fontSize: '0.8rem', letterSpacing: '0.5px' }}>
              {isRecording ? `TALKING (${duration.toFixed(1)}s)` : isCallingBackend ? 'THINKING' : isAiSpeaking ? 'SPEAKING' : 'HOLD TO TALK'}
            </span>
          </button>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Hold button or Spacebar to speak</span>
        </div>
      )}

      {/* Optional Typed Text Input Form */}
      {!isCompleted && (
        <form onSubmit={handleTextSubmit} style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <input
            type="text"
            placeholder="Or type your reply here..."
            value={typedInput}
            onChange={(e) => setTypedInput(e.target.value)}
            disabled={isCallingBackend || isRecording}
            style={{ flex: 1, padding: '10px 14px', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.9rem', outline: 'none' }}
          />
          <button
            type="submit"
            disabled={isCallingBackend || !typedInput.trim()}
            style={{ padding: '10px 18px', borderRadius: '10px', border: 'none', background: '#3b82f6', color: '#ffffff', fontWeight: 600, fontSize: '0.9rem', cursor: typedInput.trim() ? 'pointer' : 'not-allowed', opacity: typedInput.trim() ? 1 : 0.6 }}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
};
