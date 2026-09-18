import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUp, Mic, Loader2, Volume2, CheckCircle2, AlertTriangle, FileText, Globe, ChevronDown } from 'lucide-react';
import { useTranslation } from '@/hooks/useTranslation';
import { usePushToTalk } from '@/hooks/usePushToTalk';
import { AbdmLogo } from '@/assets/AbdmLogo';
import { AbhaProfile } from '@/types/abha';
import '@/styles/screen_d_chatbot.css';

interface ChatMessage {
  id: string;
  role: 'assistant' | 'patient';
  title?: string;
  text: string;
  textEnglish?: string;
  audioBase64?: string;
  isStreaming?: boolean;
}

interface TouchOptionItem {
  id: string;
  title: string;
  subtitle?: string;
  value: string;
}

const renderFormattedSummary = (content: string) => {
  const lines = content.split('\n');
  return lines.map((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return <div key={idx} style={{ height: '8px' }} />;
    }
    if (trimmed.startsWith('###') || trimmed.startsWith('##')) {
      const headerText = trimmed.replace(/^#+\s*/, '');
      return (
        <h4 key={idx} style={{ color: '#0f766e', fontWeight: 700, margin: '14px 0 4px 0', fontSize: '15px' }}>
          {headerText}
        </h4>
      );
    }
    const boldParts = trimmed.split(/(\*\*.*?\*\*)/g);
    const isBullet = trimmed.startsWith('•') || trimmed.startsWith('-');
    return (
      <div key={idx} style={{ marginLeft: isBullet ? '12px' : '0', marginBottom: '3px' }}>
        {boldParts.map((part, pIdx) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={pIdx} style={{ color: '#0f172a' }}>{part.slice(2, -2)}</strong>;
          }
          return <span key={pIdx}>{part}</span>;
        })}
      </div>
    );
  });
};

interface ScreenD_ChatbotProps {
  profile?: AbhaProfile | null;
  attachedDocument?: any;
  onBack?: () => void;
  onFinish?: (summary: string) => void;
}

export const ScreenD_Chatbot: React.FC<ScreenD_ChatbotProps> = ({
  profile,
  attachedDocument,
  onBack,
  onFinish,
}) => {
  const navigate = useNavigate();
  const { t, language, setLanguage, supportedLanguages } = useTranslation();
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isLangMenuOpen, setIsLangMenuOpen] = useState<boolean>(false);

  // Patient identification from active session
  const [activeSessionId, setActiveSessionId] = useState<string>(() => `sess_${Math.random().toString(36).substring(2, 10)}`);
  const patientId = profile?.abhaNumber || 'PAT-ROHIT-01';

  // Active language object for header display
  const currentLangObj = supportedLanguages.find((l) => l.code === language) || {
    code: 'hi',
    name: 'Hindi',
    nativeName: 'हिन्दी',
  };

  // Local Chat state
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'msg_welcome',
      role: 'assistant',
      title: t('chatbot_hello'),
      text: t('chatbot_how_help'),
    },
  ]);

  // Rehydrate full dialogue history and active patient from Kiosk DB on page mount / refresh
  useEffect(() => {
    const hydrateFromKioskDb = async () => {
      try {
        const res = await fetch('/api/v1/kiosk/session');
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            if (data.session_id) {
              setActiveSessionId(data.session_id);
            }
            if (data.messages && data.messages.length > 0) {
              setMessages(
                data.messages.map((m: any) => ({
                  id: m.id,
                  role: m.role,
                  text: m.text,
                  textEnglish: m.textEnglish,
                  audioBase64: m.audioBase64,
                }))
              );

              // Restore question-specific touch options from last assistant message
              const lastBotMsg = [...data.messages].reverse().find(
                (m: any) => m.role === 'assistant' && Array.isArray(m.touch_options) && m.touch_options.length > 0
              );
              if (lastBotMsg && lastBotMsg.touch_options.length > 0) {
                setPills(
                  lastBotMsg.touch_options.slice(0, 4).map((opt: any) => ({
                    id: opt.id,
                    title: opt.label || opt.value,
                    subtitle: opt.slot_tag || t('chatbot_symptom_tag'),
                    value: opt.value || opt.label,
                  }))
                );
              }
            }
          }
        }
      } catch (err) {
        console.warn('Could not rehydrate kiosk session from DB:', err);
      }
    };

    hydrateFromKioskDb();
  }, [t]);

  // Dynamic touch pills
  const [pills, setPills] = useState<TouchOptionItem[]>(() => [
    { id: 'opt_fever', title: t('chatbot_opt_fever'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_fever') },
    { id: 'opt_headache', title: t('chatbot_opt_headache'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_headache') },
    { id: 'opt_stomach', title: t('chatbot_opt_stomach'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_stomach') },
    { id: 'opt_chest', title: t('chatbot_opt_chest'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_chest') },
  ]);

  // Only reset default pills if conversation hasn't started yet
  useEffect(() => {
    if (messages.length <= 1) {
      setPills([
        { id: 'opt_fever', title: t('chatbot_opt_fever'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_fever') },
        { id: 'opt_headache', title: t('chatbot_opt_headache'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_headache') },
        { id: 'opt_stomach', title: t('chatbot_opt_stomach'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_stomach') },
        { id: 'opt_chest', title: t('chatbot_opt_chest'), subtitle: t('chatbot_symptom_tag'), value: t('chatbot_opt_chest') },
      ]);
    }
  }, [language, messages.length, t]);


  const [inputMessage, setInputMessage] = useState<string>('');
  const [isProcessingTurn, setIsProcessingTurn] = useState<boolean>(false);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [clinicalSummary, setClinicalSummary] = useState<string | null>(null);
  const [redFlagWarning, setRedFlagWarning] = useState<string | null>(null);

  // Audio queue & player ref for continuous streaming Sarvam voice playback (<700ms TTFA)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingAudioRef = useRef<boolean>(false);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessingTurn]);

  // Stop currently playing audio and drain queue
  const stopAudio = () => {
    audioQueueRef.current = [];
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    isPlayingAudioRef.current = false;
    setIsSpeaking(false);
  };

  // Play next audio chunk in FIFO queue
  const playNextAudioChunk = () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingAudioRef.current = false;
      setIsSpeaking(false);
      return;
    }

    const nextBase64 = audioQueueRef.current.shift();
    if (!nextBase64) {
      playNextAudioChunk();
      return;
    }

    try {
      const audio = new Audio(`data:audio/wav;base64,${nextBase64}`);
      audioPlayerRef.current = audio;
      isPlayingAudioRef.current = true;
      setIsSpeaking(true);

      audio.onended = () => {
        playNextAudioChunk();
      };
      audio.onerror = (e) => {
        console.warn('Audio chunk playback error, continuing next chunk', e);
        playNextAudioChunk();
      };
      audio.play().catch((err) => {
        console.warn('Audio play request interrupted', err);
        playNextAudioChunk();
      });
    } catch (err) {
      console.warn('Audio instantiation error', err);
      playNextAudioChunk();
    }
  };

  // Enqueue synthesized audio chunk from SSE stream
  const enqueueAudioChunk = (audioBase64?: string) => {
    if (!audioBase64) return;
    audioQueueRef.current.push(audioBase64);
    if (!isPlayingAudioRef.current) {
      playNextAudioChunk();
    }
  };

  // Central Server-Sent Events (SSE) streaming turn dispatcher
  const submitTurn = async (audioBlob?: Blob, textInput?: string, optionId?: string) => {
    if (isProcessingTurn || isCompleted) return;
    setIsProcessingTurn(true);

    // Stop any previous speech playback on new turn
    stopAudio();

    // 1. Immediately create or update user chat bubble in UI
    const tempUserText = textInput || (audioBlob ? `🎤 ${t('chatbot_transcribing')}` : (optionId ? optionId : t('chatbot_option_selected')));
    const userMsgId = liveMsgIdRef.current || `msg_user_${Date.now()}`;
    liveMsgIdRef.current = null;

    setMessages((prev) => {
      const exists = prev.some((m) => m.id === userMsgId);
      if (exists) {
        return prev.map((m) =>
          m.id === userMsgId ? { ...m, text: textInput || m.text || tempUserText } : m
        );
      }
      return [
        ...prev,
        {
          id: userMsgId,
          role: 'patient',
          text: tempUserText,
        },
      ];
    });

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
      formData.append('session_id', activeSessionId);
      formData.append('patient_id', patientId);
      formData.append('language', language);
      formData.append('hospital_type', 'allopathy');
      formData.append('max_turns', '10');

      // Include prescription OCR context if available
      if (attachedDocument) {
        const ext = attachedDocument.ocrResult?.extracted_data || attachedDocument.ocrResult;
        const hint =
          ext?.chief_complaint ||
          ext?.diagnoses?.[0]?.condition ||
          attachedDocument.name ||
          'Attached clinical prescription';
        formData.append('chief_complaint_hint', hint);
      }

      // Convert prior messages + current user message into conversation history
      const historyPayload = [
        ...messages.map((m) => ({
          role: m.role,
          content: m.textEnglish || m.text,
        })),
        {
          role: 'patient',
          content: textInput || (optionId ? optionId : tempUserText),
        },
      ];
      formData.append('conversation_history', JSON.stringify(historyPayload));

      // Attempt Server-Sent Events (SSE) streaming endpoint first (/api/v1/dialogue/stream-turn)
      let streamSucceeded = false;
      let activeBotMsgId: string | null = null;

      try {
        let response = await fetch('/api/v1/dialogue/stream-turn', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          // Fallback to interview/stream alias if needed
          response = await fetch('/api/v1/interview/stream', {
            method: 'POST',
            body: formData,
          });
        }

        if (response.ok && response.body) {
          streamSucceeded = true;
          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let buffer = '';

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split('\n\n');
            buffer = blocks.pop() || '';

            for (const block of blocks) {
              const trimmedBlock = block.trim();
              if (!trimmedBlock) continue;

              for (const line of trimmedBlock.split('\n')) {
                if (line.startsWith('data:')) {
                  const jsonStr = line.replace(/^data:\s*/, '').trim();
                  if (!jsonStr) continue;

                  try {
                    const evt = JSON.parse(jsonStr);
                    handleSseEvent(evt);
                  } catch (parseErr) {
                    console.warn('SSE JSON parse error:', parseErr, jsonStr);
                  }
                }
              }
            }
          }
        }
      } catch (streamErr) {
        console.warn('SSE streaming fetch error, falling back to standard /turn:', streamErr);
      }

      // Handle individual SSE events emitted by streaming orchestrator
      function handleSseEvent(evt: any) {
        const eventType = evt.event;

        switch (eventType) {
          case 'transcription': {
            // Update user message with transcribed speech
            const transcribedText = evt.native || evt.english;
            if (transcribedText) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === userMsgId
                    ? { ...m, text: transcribedText, textEnglish: evt.english }
                    : m
                )
              );
            }
            break;
          }

          case 'text_chunk': {
            // Stream question text into assistant bubble in real-time
            const newText = evt.text || '';
            const englishText = evt.english_text || '';

            if (!activeBotMsgId) {
              activeBotMsgId = `msg_bot_${Date.now()}`;
              const newBotMsg: ChatMessage = {
                id: activeBotMsgId,
                role: 'assistant',
                text: newText,
                textEnglish: englishText,
                isStreaming: true,
              };
              setMessages((prev) => [...prev, newBotMsg]);
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === activeBotMsgId
                    ? { ...m, text: newText, textEnglish: englishText, isStreaming: true }
                    : m
                )
              );
            }
            break;
          }

          case 'audio_chunk': {
            // Streamed synthesized Sarvam speech audio (<700ms TTFA)
            if (evt.audio_base64) {
              enqueueAudioChunk(evt.audio_base64);
            }
            break;
          }

          case 'touch_options': {
            // Update quick suggestion pills
            if (evt.touch_options && Array.isArray(evt.touch_options) && evt.touch_options.length > 0) {
              const newPills: TouchOptionItem[] = evt.touch_options.slice(0, 4).map((opt: any) => ({
                id: opt.id,
                title: opt.label || opt.value,
                subtitle: opt.slot_tag || t('chatbot_symptom_tag'),
                value: opt.value || opt.label,
              }));
              setPills(newPills);
            }
            break;
          }

          case 'red_flag': {
            // Emergency clinical triage alert
            setRedFlagWarning(evt.message || 'Critical emergency symptom detected.');
            if (evt.audio_base64) {
              enqueueAudioChunk(evt.audio_base64);
            }
            break;
          }

          case 'summary': {
            // Clinical intake summary
            if (evt.clinical_summary) {
              setClinicalSummary(evt.clinical_summary);
            }
            if (evt.closing_message) {
              if (!activeBotMsgId) {
                activeBotMsgId = `msg_bot_${Date.now()}`;
                setMessages((prev) => [
                  ...prev,
                  { id: activeBotMsgId!, role: 'assistant', text: evt.closing_message },
                ]);
              } else {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === activeBotMsgId ? { ...m, text: evt.closing_message, isStreaming: false } : m
                  )
                );
              }
            }
            if (evt.closing_audio_base64) {
              enqueueAudioChunk(evt.closing_audio_base64);
            }
            break;
          }

          case 'done': {
            if (evt.is_completed) {
              setIsCompleted(true);
            }
            if (activeBotMsgId) {
              setMessages((prev) =>
                prev.map((m) => (m.id === activeBotMsgId ? { ...m, isStreaming: false } : m))
              );
            }
            break;
          }

          default:
            break;
        }
      }

      // Fallback: If streaming wasn't available, hit standard /turn endpoint
      if (!streamSucceeded) {
        const fbResponse = await fetch('/api/v1/interview/turn', {
          method: 'POST',
          body: formData,
        });

        if (!fbResponse.ok) {
          throw new Error(`Server error: HTTP ${fbResponse.status}`);
        }

        const data = await fbResponse.json();

        // Update patient utterance
        const userText =
          data.patient_utterance?.native ||
          textInput ||
          (audioBlob ? `🎤 ${t('chatbot_voice_response')}` : t('chatbot_option_selected'));

        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsgId
              ? { ...m, text: userText, textEnglish: data.patient_utterance?.english }
              : m
          )
        );

        if (data.red_flag_alert?.is_red_flag) {
          setRedFlagWarning(data.red_flag_alert.emergency_message || 'Critical emergency symptom detected.');
        }

        if (data.next_question) {
          const botMsg: ChatMessage = {
            id: `msg_bot_${Date.now()}`,
            role: 'assistant',
            text: data.next_question.native || data.next_question.english,
            textEnglish: data.next_question.english,
          };
          setMessages((prev) => [...prev, botMsg]);
          enqueueAudioChunk(data.audio_response?.audio_base64);
        } else if (data.is_completed && data.closing_message) {
          const closingMsg: ChatMessage = {
            id: `msg_closing_${Date.now()}`,
            role: 'assistant',
            text: data.closing_message.native || data.closing_message.english,
            textEnglish: data.closing_message.english,
          };
          setMessages((prev) => [...prev, closingMsg]);
          enqueueAudioChunk(data.audio_response?.audio_base64);
        }

        if (data.touch_options && data.touch_options.length > 0) {
          const newPills: TouchOptionItem[] = data.touch_options.slice(0, 4).map((opt: any) => ({
            id: opt.id,
            title: opt.label_native || opt.label,
            subtitle: opt.slot_tag || t('chatbot_symptom_tag'),
            value: opt.value || opt.label,
          }));
          setPills(newPills);
        }

        if (data.is_completed) {
          setIsCompleted(true);
          if (data.clinical_summary) {
            setClinicalSummary(data.clinical_summary);
          }
        }
      }
    } catch (err: any) {
      console.error('Turn submission error:', err);
    } finally {
      setIsProcessingTurn(false);
    }
  };

  // Real-time Speech WebSocket references
  const speechWsRef = useRef<WebSocket | null>(null);
  const liveMsgIdRef = useRef<string | null>(null);
  const receivedFinalViaWsRef = useRef<boolean>(false);

  // Push-To-Talk Voice integration for the lime green bottom button
  const { isRecording, isProcessing: isVoiceProcessing, startRecording, stopRecording } = usePushToTalk({
    onAudioChunk: (chunk: Float32Array) => {
      if (speechWsRef.current && speechWsRef.current.readyState === WebSocket.OPEN) {
        const int16 = new Int16Array(chunk.length);
        for (let i = 0; i < chunk.length; i++) {
          const s = Math.max(-1, Math.min(1, chunk[i]));
          int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        speechWsRef.current.send(int16.buffer);
      }
    },
    onAudioReady: async (result) => {
      if (!result.blob) return;
      if (receivedFinalViaWsRef.current) {
        return;
      }
      await submitTurn(result.blob, undefined, undefined);
    },
  });

  const handleMicClick = () => {
    if (isRecording) {
      if (speechWsRef.current && speechWsRef.current.readyState === WebSocket.OPEN) {
        speechWsRef.current.send(JSON.stringify({ event: 'stop' }));
      }
      stopRecording();
    } else {
      receivedFinalViaWsRef.current = false;
      const msgId = `msg_user_${Date.now()}`;
      liveMsgIdRef.current = msgId;

      try {
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProto}//${window.location.host}/api/v1/ws/speech?language=${language}&session_id=${activeSessionId}`;
        const ws = new WebSocket(wsUrl);
        speechWsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.event === 'partial' && data.transcript) {
              setMessages((prev) => {
                const targetId = liveMsgIdRef.current;
                if (!targetId) return prev;
                const existing = prev.some((m) => m.id === targetId);
                if (existing) {
                  return prev.map((m) =>
                    m.id === targetId ? { ...m, text: data.transcript } : m
                  );
                } else {
                  return [
                    ...prev,
                    {
                      id: targetId,
                      role: 'patient',
                      text: data.transcript,
                    },
                  ];
                }
              });
            } else if (data.event === 'final' && data.native) {
              receivedFinalViaWsRef.current = true;
              submitTurn(undefined, data.native, undefined);
            }
          } catch (e) {
            console.debug('Speech WS parse err', e);
          }
        };

        ws.onerror = (err) => {
          console.warn('Speech WS error, fallback to audio upload', err);
        };

        ws.onclose = () => {
          speechWsRef.current = null;
        };
      } catch (err) {
        console.warn('Speech WS connection error:', err);
      }

      startRecording();
    }
  };

  const handleTextSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || isProcessingTurn) return;
    setInputMessage('');
    submitTurn(undefined, trimmed, undefined);
  };

  const handlePillClick = (pill: TouchOptionItem) => {
    if (isProcessingTurn || isCompleted) return;
    submitTurn(undefined, pill.title, pill.id);
  };

  const handleBack = () => {
    stopAudio();
    if (onBack) {
      onBack();
    } else {
      navigate('/profile');
    }
  };

  return (
    <div className="figma-chatbot-screen">
      {/* 1. TOP HEADER (Back Button, Center Logo, Language Switcher, Right ABDM Emblem) */}
      <header className="figma-chatbot-header">
        <button
          onClick={handleBack}
          className="figma-chatbot-back-btn"
          title={t('back_to_profile')}
          aria-label={t('back_to_profile')}
        >
          <div className="figma-chatbot-bar" style={{ width: '32px' }} />
          <div className="figma-chatbot-bar" style={{ width: '52px' }} />
          <div className="figma-chatbot-bar" style={{ width: '13px' }} />
        </button>

        <div className="figma-chatbot-logo" onClick={() => navigate('/profile')}>
          <span className="figma-chatbot-logo-text">MediKiosk</span>
        </div>

        <div className="figma-chatbot-header-actions">
          {/* Active Language Switcher Dropdown */}
          <div className="figma-chatbot-lang-container">
            <button
              type="button"
              className="figma-chatbot-lang-btn"
              onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
              title="Change Language"
            >
              <Globe size={18} color="#34C759" />
              <span>{currentLangObj.name} ({currentLangObj.nativeName})</span>
              <ChevronDown size={15} color="#64748b" />
            </button>

            {isLangMenuOpen && (
              <div className="figma-chatbot-lang-menu">
                {supportedLanguages.map((l) => (
                  <div
                    key={l.code}
                    className={`figma-chatbot-lang-item ${language === l.code ? 'active' : ''}`}
                    onClick={() => {
                      setLanguage(l.code);
                      setIsLangMenuOpen(false);
                    }}
                  >
                    <span className="figma-chatbot-lang-item-name">{l.name}</span>
                    <span className="figma-chatbot-lang-item-native">{l.nativeName}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="figma-chatbot-abdm">
            <AbdmLogo size={90} />
          </div>
        </div>
      </header>

      {/* 2. CHAT STREAM DIALOGUE AREA */}
      <main className="figma-chatbot-dialogue-area">
        {attachedDocument && (
          <div className="figma-chatbot-attached-badge">
            <FileText size={16} />
            <span>{t('chatbot_attached_doc')} {attachedDocument.name || 'Clinical Prescription'}</span>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={msg.role === 'assistant' ? 'figma-chatbot-bubble-bot' : 'figma-chatbot-bubble-patient'}
          >
            {msg.title && <h2 className="figma-chatbot-bot-title">{msg.title}</h2>}
            <p className="figma-chatbot-bot-text">
              {msg.text}
              {msg.isStreaming && <span className="figma-chatbot-stream-cursor" />}
            </p>
            {msg.role === 'assistant' && isSpeaking && (
              <div
                className="figma-chatbot-speaking-badge"
                onClick={stopAudio}
                title="Click to mute"
              >
                <Volume2 size={15} className="animate-pulse" />
                <span>{t('chatbot_ai_speaking')}</span>
              </div>
            )}
          </div>
        ))}

        {isProcessingTurn && (
          <div className="figma-chatbot-bubble-bot" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Loader2 className="animate-spin" size={20} color="#34C759" />
            <span style={{ fontSize: '16px', color: '#64748b' }}>{t('chatbot_processing')}</span>
          </div>
        )}

        {/* Emergency Red Flag Alert Notification */}
        {redFlagWarning && (
          <div className="figma-chatbot-redflag-alert">
            <AlertTriangle size={26} color="#dc2626" />
            <div>
              <div className="figma-chatbot-redflag-title">{t('chatbot_critical_alert')}</div>
              <div className="figma-chatbot-redflag-desc">{redFlagWarning}</div>
            </div>
          </div>
        )}

        {/* Consultation Complete Summary Card */}
        {isCompleted && clinicalSummary && (
          <div className="figma-chatbot-summary-card">
            <div className="figma-chatbot-summary-header">
              <CheckCircle2 size={24} color="#16a34a" />
              <h3 className="figma-chatbot-summary-title">{t('chatbot_intake_completed')}</h3>
            </div>
            <div className="figma-chatbot-summary-body">{renderFormattedSummary(clinicalSummary)}</div>
            <div className="figma-chatbot-summary-actions">
              <button
                className="figma-chatbot-btn-finish"
                onClick={() => {
                  if (onFinish) onFinish(clinicalSummary);
                  navigate('/profile');
                }}
              >
                {t('chatbot_proceed_doctor')}
              </button>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </main>

      {/* 3. QUICK-SELECT SUGGESTION PILLS */}
      {!isCompleted && (
        <section className="figma-chatbot-pills-row" aria-label="Quick symptom options">
          {isProcessingTurn ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', color: '#64748b', fontSize: '14px', background: 'rgba(255,255,255,0.7)', borderRadius: '20px' }}>
              <Loader2 className="animate-spin" size={16} color="#34C759" />
              <span>{t('chatbot_processing')}</span>
            </div>
          ) : (
            pills.map((pill) => (
              <button
                key={pill.id}
                className="figma-chatbot-pill-btn"
                onClick={() => handlePillClick(pill)}
                disabled={isProcessingTurn}
              >
                <span className="figma-chatbot-pill-title">{pill.title}</span>
                {pill.subtitle && <span className="figma-chatbot-pill-subtitle">{pill.subtitle}</span>}
              </button>
            ))
          )}
        </section>
      )}

      {/* 4. MESSAGE INPUT BAR */}
      {!isCompleted && (
        <form className="figma-chatbot-input-bar" onSubmit={handleTextSubmit}>
          <input
            type="text"
            className="figma-chatbot-input-field"
            placeholder={t('chatbot_message_placeholder')}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={isProcessingTurn || isRecording}
          />
          <button
            type="submit"
            className="figma-chatbot-send-btn"
            disabled={!inputMessage.trim() || isProcessingTurn}
            aria-label="Send message"
          >
            <ArrowUp size={22} strokeWidth={3} />
          </button>
        </form>
      )}

      {/* 5. BOTTOM MICROPHONE SECTION */}
      {!isCompleted && (
        <footer className="figma-chatbot-mic-section">
          <div className={`figma-chatbot-mic-label ${isRecording ? 'recording' : ''}`}>
            {isRecording
              ? t('chatbot_listening')
              : (isVoiceProcessing || isProcessingTurn)
                ? t('chatbot_transcribing')
                : t('chatbot_tap_to_speak')}
          </div>

          <button
            type="button"
            className={`figma-chatbot-mic-btn ${isRecording ? 'recording' : ''}`}
            onClick={handleMicClick}
            disabled={isProcessingTurn}
            aria-label={t('chatbot_tap_to_speak')}
          >
            <Mic className="figma-chatbot-mic-icon" />
          </button>
        </footer>
      )}
    </div>
  );
};

export default ScreenD_Chatbot;
