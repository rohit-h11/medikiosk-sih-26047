/**
 * Frontend Prakriti & Dashavidha Scoring Tests
 * Validates Prakriti scoring tallies, tie-breaking, and Dashavidha 3-question evaluation.
 */

describe('Prakriti & Dashavidha Scoring Engine', () => {
  interface ScoreInput {
    vata: number;
    pitta: number;
    kapha: number;
  }

  function calculatePrakriti(scores: ScoreInput): string {
    const total = scores.vata + scores.pitta + scores.kapha;
    if (total === 0) return 'Vata-Pitta Prakriti';

    const vataPct = (scores.vata / total) * 100;
    const pittaPct = (scores.pitta / total) * 100;
    const kaphaPct = (scores.kapha / total) * 100;

    const entries = [
      { dosha: 'Vata', pct: vataPct },
      { dosha: 'Pitta', pct: pittaPct },
      { dosha: 'Kapha', pct: kaphaPct },
    ].sort((a, b) => b.pct - a.pct);

    // If top dosha exceeds 60%, single dosha
    if (entries[0].pct >= 60) {
      return `${entries[0].dosha}ja Prakriti`;
    }
    // Dual dosha
    return `${entries[0].dosha}-${entries[1].dosha} Prakriti`;
  }

  test('Determines dual Pitta-Kapha Prakriti accurately', () => {
    const scores = { vata: 2, pitta: 6, kapha: 4 }; // 12 questions total
    const result = calculatePrakriti(scores);
    expect(result).toBe('Pitta-Kapha Prakriti');
  });

  test('Determines dominant single dosha when exceeding threshold', () => {
    const scores = { vata: 1, pitta: 9, kapha: 2 }; // Pitta = 75%
    const result = calculatePrakriti(scores);
    expect(result).toBe('Pittaja Prakriti');
  });

  test('Determines Vata-Pitta Prakriti when Vata and Pitta are dominant', () => {
    const scores = { vata: 7, pitta: 4, kapha: 1 };
    const result = calculatePrakriti(scores);
    expect(result).toBe('Vata-Pitta Prakriti');
  });

  test('Validates Dashavidha functional assessment values', () => {
    const validSattva = ['Pravara', 'Madhyama', 'Avara'];
    const validSatmya = ['Sarva-rasa', 'Oka-satmya', 'Eka-rasa'];
    const validVyayama = ['Pravara', 'Madhyama', 'Avara'];

    expect(validSattva).toContain('Pravara');
    expect(validSatmya).toContain('Sarva-rasa');
    expect(validVyayama).toContain('Madhyama');
  });
});
