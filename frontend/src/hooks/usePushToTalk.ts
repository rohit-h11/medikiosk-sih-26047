/**
 * MediKiosk Push-To-Talk React Hook
 * Provides full push-to-talk state management, hold-to-talk event binders,
 * real-time volume telemetry, automatic Web Audio DSP preprocessing, and ASR payload dispatch.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  PushToTalkState,
  ProcessedAudioResult,
  UsePushToTalkOptions,
  PushToTalkBindings,
} from '@/types/audio';
import { createAudioGraph, LiveAudioGraph } from '@/utils/audio/audioGraph';
import { preprocessAudio } from '@/utils/audio/audioPreprocessor';

export function usePushToTalk(options: UsePushToTalkOptions = {}) {
  const { config, onAudioReady, onStateChange, onError, onVolumeChange } = options;

  const [state, setState] = useState<PushToTalkState>('idle');
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [error, setError] = useState<Error | null>(null);
  const [lastResult, setLastResult] = useState<ProcessedAudioResult | null>(null);

  // References to keep tracking across renders without recreating functions
  const stateRef = useRef<PushToTalkState>('idle');
  const audioGraphRef = useRef<LiveAudioGraph | null>(null);
  const startTimeRef = useRef<number>(0);
  const timerIntervalRef = useRef<number | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const isHoldingKeyRef = useRef<boolean>(false);
  const maxTimeoutRef = useRef<number | null>(null);

  // Notify state changes
  const updateState = useCallback(
    (newState: PushToTalkState) => {
      stateRef.current = newState;
      setState(newState);
      onStateChange?.(newState);
    },
    [onStateChange]
  );

  // Cleanup helper to stop animation frame, timers, and active audio graphs
  const cleanupResources = useCallback(() => {
    if (timerIntervalRef.current) {
      window.clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (animFrameRef.current) {
      window.cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (maxTimeoutRef.current) {
      window.clearTimeout(maxTimeoutRef.current);
      maxTimeoutRef.current = null;
    }
    if (audioGraphRef.current) {
      audioGraphRef.current.stop();
      audioGraphRef.current = null;
    }
    setVolumeLevel(0);
    onVolumeChange?.(0);
  }, [onVolumeChange]);

  // Cancel recording without saving/processing
  const cancelRecording = useCallback(() => {
    cleanupResources();
    setDuration(0);
    updateState('idle');
  }, [cleanupResources, updateState]);

  // Stop recording, run DSP preprocessing, encode to 16kHz WAV, and return result
  const stopRecording = useCallback(async (): Promise<ProcessedAudioResult | null> => {
    if (!audioGraphRef.current || state !== 'recording') {
      return null;
    }

    const elapsedMs = Date.now() - startTimeRef.current;
    const minDurationMs = config?.minDurationMs ?? 350;

    // Accidental tap check: if user tapped < minDurationMs, cancel to prevent glitch
    if (elapsedMs < minDurationMs) {
      console.warn(`Recording was too short (${elapsedMs}ms < ${minDurationMs}ms). Ignored.`);
      cancelRecording();
      return null;
    }

    updateState('processing');

    const graph = audioGraphRef.current;
    const rawSamples = graph.getRawSamples();
    const sourceSampleRate = graph.audioContext.sampleRate;

    cleanupResources();

    try {
      // Run the DSP preprocessing pipeline (Resampling to 16kHz, Silence Trim, Peak Norm, WAV Encode)
      const result = preprocessAudio(rawSamples, sourceSampleRate, config);

      setLastResult(result);
      updateState('completed');

      // Trigger optional callback for consumer or API layer
      if (onAudioReady) {
        await onAudioReady(result);
      }

      return result;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      onError?.(e);
      updateState('error');
      return null;
    }
  }, [state, config, cleanupResources, updateState, cancelRecording, onAudioReady, onError]);

  // Start recording
  const startRecording = useCallback(async () => {
    // If already recording or processing, ignore
    if (state === 'recording' || state === 'processing' || state === 'preparing') {
      return;
    }

    setError(null);
    updateState('preparing');

    try {
      // 1. Build and connect Web Audio DSP graph with 85Hz HighPass + DynamicsCompressor
      const graph = await createAudioGraph(config);
      audioGraphRef.current = graph;
      startTimeRef.current = Date.now();

      updateState('recording');

      // 2. Start duration timer
      timerIntervalRef.current = window.setInterval(() => {
        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        setDuration(elapsed);
      }, 50);

      // 3. Start real-time volume level update loop (60fps)
      const updateVolumeLoop = () => {
        if (audioGraphRef.current) {
          const vol = audioGraphRef.current.getCurrentVolume();
          setVolumeLevel(vol);
          onVolumeChange?.(vol);
          animFrameRef.current = window.requestAnimationFrame(updateVolumeLoop);
        }
      };
      animFrameRef.current = window.requestAnimationFrame(updateVolumeLoop);

      // 4. Safety max duration timeout
      const maxMs = config?.maxDurationMs ?? 30000;
      maxTimeoutRef.current = window.setTimeout(() => {
        if (stateRef.current === 'recording') {
          stopRecording();
        }
      }, maxMs);
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      onError?.(e);
      updateState('error');
      cleanupResources();
    }
  }, [config, updateState, onVolumeChange, onError, cleanupResources, stopRecording]);

  // Toggle mode (start if idle, stop if recording)
  const toggleRecording = useCallback(() => {
    if (stateRef.current === 'recording') {
      stopRecording();
    } else if (
      stateRef.current === 'idle' ||
      stateRef.current === 'completed' ||
      stateRef.current === 'error'
    ) {
      startRecording();
    }
  }, [startRecording, stopRecording]);

  // Push-to-Talk Event Bindings for React components
  const bindPushToTalk = useCallback((): PushToTalkBindings & {
    tabIndex: number;
    role: string;
    'aria-label': string;
  } => {
    return {
      tabIndex: 0,
      role: 'button',
      'aria-label': 'Push to Talk Microphone Button',

      onMouseDown: (e: React.MouseEvent) => {
        if (e.button === 0) {
          // Left click only
          e.preventDefault();
          startRecording();
        }
      },
      onMouseUp: (e: React.MouseEvent) => {
        if (e.button === 0) {
          e.preventDefault();
          stopRecording();
        }
      },
      onTouchStart: (e: React.TouchEvent) => {
        e.preventDefault();
        startRecording();
      },
      onTouchEnd: (e: React.TouchEvent) => {
        e.preventDefault();
        stopRecording();
      },
      onTouchCancel: (e: React.TouchEvent) => {
        e.preventDefault();
        cancelRecording();
      },
      onKeyDown: (e: React.KeyboardEvent) => {
        if ((e.code === 'Space' || e.key === ' ') && !isHoldingKeyRef.current) {
          isHoldingKeyRef.current = true;
          e.preventDefault();
          startRecording();
        }
      },
      onKeyUp: (e: React.KeyboardEvent) => {
        if (e.code === 'Space' || e.key === ' ') {
          isHoldingKeyRef.current = false;
          e.preventDefault();
          stopRecording();
        }
      },
    };
  }, [startRecording, stopRecording, cancelRecording]);

  // Cleanup on component unmount
  useEffect(() => {
    return () => {
      cleanupResources();
    };
  }, [cleanupResources]);

  return {
    state,
    isRecording: state === 'recording',
    isProcessing: state === 'processing',
    isPreparing: state === 'preparing',
    isCompleted: state === 'completed',
    isError: state === 'error',
    volumeLevel,
    duration,
    error,
    lastResult,
    stats: lastResult?.stats ?? null,
    audioBlob: lastResult?.blob ?? null,
    previewUrl: lastResult?.previewUrl ?? null,
    startRecording,
    stopRecording,
    cancelRecording,
    toggleRecording,
    bindPushToTalk,
    audioGraph: audioGraphRef.current,
  };
}
