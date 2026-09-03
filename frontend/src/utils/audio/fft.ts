/**
 * Fast Fourier Transform (FFT) & Inverse FFT (IFFT) in Pure TypeScript
 * Implements Cooley-Tukey Radix-2 in-place algorithm for power-of-two window sizes (e.g. N = 512).
 */

export class FFT {
  public size: number;
  private cosTable: Float32Array;
  private sinTable: Float32Array;
  private bitReverseTable: Uint32Array;

  constructor(size: number = 512) {
    if ((size & (size - 1)) !== 0) {
      throw new Error(`FFT size must be a power of 2, received ${size}`);
    }
    this.size = size;

    // Precompute twiddle factor trigonometry tables
    this.cosTable = new Float32Array(size / 2);
    this.sinTable = new Float32Array(size / 2);
    for (let i = 0; i < size / 2; i++) {
      const angle = (-2 * Math.PI * i) / size;
      this.cosTable[i] = Math.cos(angle);
      this.sinTable[i] = Math.sin(angle);
    }

    // Precompute bit reversal lookup table
    this.bitReverseTable = new Uint32Array(size);
    const bits = Math.log2(size);
    for (let i = 0; i < size; i++) {
      let rev = 0;
      let val = i;
      for (let j = 0; j < bits; j++) {
        rev = (rev << 1) | (val & 1);
        val >>= 1;
      }
      this.bitReverseTable[i] = rev;
    }
  }

  /**
   * Forward FFT: Converts time-domain real/imag arrays to frequency domain in-place.
   */
  public forward(real: Float32Array, imag: Float32Array): void {
    const n = this.size;

    // 1. Bit-reversal permutation
    for (let i = 0; i < n; i++) {
      const j = this.bitReverseTable[i];
      if (j > i) {
        const tempR = real[i];
        real[i] = real[j];
        real[j] = tempR;

        const tempI = imag[i];
        imag[i] = imag[j];
        imag[j] = tempI;
      }
    }

    // 2. Cooley-Tukey butterfly computations
    for (let halfSize = 1; halfSize < n; halfSize *= 2) {
      const step = halfSize * 2;
      const tableStep = n / step;

      for (let i = 0; i < n; i += step) {
        for (let j = 0; j < halfSize; j++) {
          const k = j * tableStep;
          const c = this.cosTable[k];
          const s = this.sinTable[k];

          const matchIdx = i + j + halfSize;
          const uR = real[i + j];
          const uI = imag[i + j];

          const vR = real[matchIdx] * c - imag[matchIdx] * s;
          const vI = real[matchIdx] * s + imag[matchIdx] * c;

          real[i + j] = uR + vR;
          imag[i + j] = uI + vI;
          real[matchIdx] = uR - vR;
          imag[matchIdx] = uI - vI;
        }
      }
    }
  }

  /**
   * Inverse FFT: Converts frequency-domain real/imag arrays back to time domain in-place.
   */
  public inverse(real: Float32Array, imag: Float32Array): void {
    const n = this.size;

    // Conjugate input
    for (let i = 0; i < n; i++) {
      imag[i] = -imag[i];
    }

    // Forward FFT
    this.forward(real, imag);

    // Conjugate and normalize by N
    for (let i = 0; i < n; i++) {
      real[i] /= n;
      imag[i] = -imag[i] / n;
    }
  }
}
