/**
 * MediKiosk Voice & Audio Context
 * Centralized state provider for active language selection, microphone permissions,
 * DSP audio configuration, and pluggable audio pipeline handlers.
 */

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { AudioProcessingConfig, ProcessedAudioResult } from '@/types/audio';

export interface SupportedLanguage {
  code: string;
  name: string;
  nativeName: string;
}

export const INDIAN_LANGUAGES: SupportedLanguage[] = [
  { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी' },
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'ta', name: 'Tamil', nativeName: 'தமிழ்' },
  { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
  { code: 'mr', name: 'Marathi', nativeName: 'मराठी' },
  { code: 'bn', name: 'Bengali', nativeName: 'বাংলা' },
  { code: 'gu', name: 'Gujarati', nativeName: 'ગુજરાતી' },
  { code: 'kn', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
  { code: 'ml', name: 'Malayalam', nativeName: 'മലയാളം' },
  { code: 'pa', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ' },
  { code: 'or', name: 'Odia', nativeName: 'ଓଡ଼ିଆ' },
  { code: 'as', name: 'Assamese', nativeName: 'অসমীয়া' },
];

export interface VoiceContextValue {
  /** Active language code (e.g. 'hi', 'ta', 'te', 'en') */
  language: string;
  /** Set current active kiosk language */
  setLanguage: (lang: string) => void;
  /** Full list of supported Indian languages */
  supportedLanguages: SupportedLanguage[];
  /** Audio processing configuration */
  audioConfig: AudioProcessingConfig;
  /** Update audio configuration */
  updateAudioConfig: (config: Partial<AudioProcessingConfig>) => void;
  /** Microphone permission status: null (unknown), true (granted), false (denied) */
  micPermission: boolean | null;
  /** Explicitly request mic permission early during kiosk initialization */
  requestMicPermission: () => Promise<boolean>;
  /** Most recent preprocessed audio result */
  lastResult: ProcessedAudioResult | null;
  /** Update latest audio result */
  setLastResult: (result: ProcessedAudioResult | null) => void;
}

const VoiceContext = createContext<VoiceContextValue | undefined>(undefined);

export interface VoiceProviderProps {
  children: React.ReactNode;
  defaultLanguage?: string;
  initialConfig?: AudioProcessingConfig;
}

export const VoiceProvider: React.FC<VoiceProviderProps> = ({
  children,
  defaultLanguage = 'hi',
  initialConfig = {},
}) => {
  const [language, setLanguage] = useState<string>(defaultLanguage);
  const [audioConfig, setAudioConfig] = useState<AudioProcessingConfig>({
    targetSampleRate: 16000,
    noiseSuppression: true,
    echoCancellation: true,
    autoGainControl: false,
    enableHighPassFilter: true,
    highPassCutoff: 110,
    enableCompression: false,
    enableSpectralDenoise: true,
    spectralDenoiseStrength: 1.0,
    enableNoiseGate: false,
    noiseGateThreshold: 0.007,
    trimSilence: true,
    silenceRmsThreshold: 0.007,
    silencePaddingSec: 0.20,
    normalizePeak: false,
    targetPeak: 0.90,
    minDurationMs: 350,
    maxDurationMs: 30000,
    ...initialConfig,
  });

  const [micPermission, setMicPermission] = useState<boolean | null>(null);
  const [lastResult, setLastResult] = useState<ProcessedAudioResult | null>(null);

  const updateAudioConfig = useCallback((partial: Partial<AudioProcessingConfig>) => {
    setAudioConfig((prev) => ({ ...prev, ...partial }));
  }, []);

  const requestMicPermission = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission(true);
      return true;
    } catch (err) {
      console.warn('Microphone permission request failed:', err);
      setMicPermission(false);
      return false;
    }
  }, []);

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      supportedLanguages: INDIAN_LANGUAGES,
      audioConfig,
      updateAudioConfig,
      micPermission,
      requestMicPermission,
      lastResult,
      setLastResult,
    }),
    [language, audioConfig, updateAudioConfig, micPermission, requestMicPermission, lastResult]
  );

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
};

export function useVoiceContext(): VoiceContextValue {
  const context = useContext(VoiceContext);
  if (!context) {
    throw new Error('useVoiceContext must be used within a VoiceProvider');
  }
  return context;
}
