/**
 * MediKiosk General Audio Recorder Hook
 * Standard toggle-based (start/stop/pause/resume) audio recording with automatic DSP preprocessing.
 */

import { useState, useRef, useCallback } from 'react';
import { ProcessedAudioResult, AudioProcessingConfig } from '@/types/audio';
import { createAudioGraph, LiveAudioGraph } from '@/utils/audio/audioGraph';
import { preprocessAudio } from '@/utils/audio/audioPreprocessor';

export function useAudioRecorder(config?: AudioProcessingConfig) {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [duration, setDuration] = useState<number>(0);
  const [volume, setVolume] = useState<number>(0);
  const [audioResult, setAudioResult] = useState<ProcessedAudioResult | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const audioGraphRef = useRef<LiveAudioGraph | null>(null);
  const timerRef = useRef<number | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  const start = useCallback(async () => {
    try {
      setError(null);
      const graph = await createAudioGraph(config);
      audioGraphRef.current = graph;
      startTimeRef.current = Date.now();

      setIsRecording(true);
      setIsPaused(false);

      timerRef.current = window.setInterval(() => {
        setDuration((Date.now() - startTimeRef.current) / 1000);
      }, 50);

      const loop = () => {
        if (audioGraphRef.current) {
          setVolume(audioGraphRef.current.getCurrentVolume());
          animFrameRef.current = window.requestAnimationFrame(loop);
        }
      };
      animFrameRef.current = window.requestAnimationFrame(loop);
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      setIsRecording(false);
    }
  }, [config]);

  const stop = useCallback(async (): Promise<ProcessedAudioResult | null> => {
    if (!audioGraphRef.current || !isRecording) return null;

    if (timerRef.current) clearInterval(timerRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);

    setIsRecording(false);
    setIsProcessing(true);

    const graph = audioGraphRef.current;
    const rawSamples = graph.getRawSamples();
    const sourceSampleRate = graph.audioContext.sampleRate;
    graph.stop();
    audioGraphRef.current = null;

    try {
      const result = preprocessAudio(rawSamples, sourceSampleRate, config);
      setAudioResult(result);
      setIsProcessing(false);
      return result;
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setError(e);
      setIsProcessing(false);
      return null;
    }
  }, [isRecording, config]);

  const cancel = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (audioGraphRef.current) {
      audioGraphRef.current.stop();
      audioGraphRef.current = null;
    }
    setIsRecording(false);
    setIsPaused(false);
    setIsProcessing(false);
    setDuration(0);
    setVolume(0);
  }, []);

  return {
    isRecording,
    isPaused,
    isProcessing,
    duration,
    volume,
    audioResult,
    error,
    start,
    stop,
    cancel,
    audioGraph: audioGraphRef.current,
  };
}
