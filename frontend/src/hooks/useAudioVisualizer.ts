/**
 * MediKiosk Audio Visualizer React Hook
 * Provides high-performance 60fps audio waveform and frequency spectrum telemetry
 * for rendering interactive UI visualizers, pulsing voice rings, and oscilloscope bars on canvas.
 */

import { useEffect, useRef, useCallback } from 'react';

export interface VisualizerOptions {
  /** Canvas ref or HTMLElement */
  canvasRef?: React.RefObject<HTMLCanvasElement>;
  /** AnalyserNode from Web Audio API */
  analyserNode?: AnalyserNode | null;
  /** Visualizer mode: 'bars' | 'wave' | 'circle' */
  mode?: 'bars' | 'wave' | 'circle';
  /** Primary accent color (hex or rgb) */
  primaryColor?: string;
  /** Secondary accent color (hex or rgb) */
  secondaryColor?: string;
  /** FFT size for frequency resolution (default 256) */
  fftSize?: number;
}

export function useAudioVisualizer(options: VisualizerOptions = {}) {
  const {
    canvasRef,
    analyserNode,
    mode = 'bars',
    primaryColor = '#0284c7', // Tailwind Sky-600
    secondaryColor = '#38bdf8', // Tailwind Sky-400
  } = options;

  const animationFrameRef = useRef<number | null>(null);

  const draw = useCallback(() => {
    if (!canvasRef?.current || !analyserNode) {
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const bufferLength = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    if (mode === 'wave') {
      analyserNode.getByteTimeDomainData(dataArray);

      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 3;
      ctx.strokeStyle = primaryColor;
      ctx.beginPath();

      const sliceWidth = (width * 1.0) / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * height) / 2;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }

        x += sliceWidth;
      }

      ctx.lineTo(width, height / 2);
      ctx.stroke();
    } else if (mode === 'bars') {
      analyserNode.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, width, height);

      const barCount = 32;
      const step = Math.floor(bufferLength / barCount);
      const barWidth = (width / barCount) * 0.75;
      const barSpacing = (width / barCount) * 0.25;

      const gradient = ctx.createLinearGradient(0, height, 0, 0);
      gradient.addColorStop(0, primaryColor);
      gradient.addColorStop(1, secondaryColor);
      ctx.fillStyle = gradient;

      for (let i = 0; i < barCount; i++) {
        const value = dataArray[i * step] || 0;
        const barHeight = (value / 255) * height;
        const x = i * (barWidth + barSpacing);
        const y = height - barHeight;

        // Rounded top bars
        const radius = Math.min(barWidth / 2, 4);
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + barWidth - radius, y);
        ctx.quadraticCurveTo(x + barWidth, y, x + barWidth, y + radius);
        ctx.lineTo(x + barWidth, height);
        ctx.lineTo(x, height);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
        ctx.fill();
      }
    }

    animationFrameRef.current = window.requestAnimationFrame(draw);
  }, [canvasRef, analyserNode, mode, primaryColor, secondaryColor]);

  useEffect(() => {
    if (analyserNode && canvasRef?.current) {
      animationFrameRef.current = window.requestAnimationFrame(draw);
    }

    return () => {
      if (animationFrameRef.current) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [analyserNode, draw, canvasRef]);

  return {
    isVisualizing: Boolean(analyserNode),
  };
}
