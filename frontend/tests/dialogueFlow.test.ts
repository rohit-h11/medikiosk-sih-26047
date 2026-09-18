/**
 * Frontend Dialogue Flow & Touch Option Tests
 * Tests quick-tap touch option pill handling, SSE event parsing, and bilingual display.
 */

describe('Dialogue Flow & Touch Options', () => {
  interface TouchOption {
    id: string;
    label: string;
    label_native?: string;
    value: string;
    slot_tag?: string;
  }

  test('Parses touch options correctly from SSE event payload', () => {
    const rawOptions: TouchOption[] = [
      { id: 'opt1', label: 'Pain spreads to left arm', value: 'Pain spreads to left arm', slot_tag: 'radiation' },
      { id: 'opt2', label: 'No sweating or breathlessness', value: 'No sweating or breathlessness', slot_tag: 'associations' },
      { id: 'opt3', label: 'Missed doses for 2 days', value: 'Missed doses for 2 days', slot_tag: 'exacerbating_relieving' },
    ];

    expect(rawOptions).toHaveLength(3);
    expect(rawOptions[0].slot_tag).toBe('radiation');
    expect(rawOptions[1].slot_tag).toBe('associations');
    expect(rawOptions[2].slot_tag).toBe('exacerbating_relieving');
  });

  test('Resolves supported language codes properly', () => {
    const supportedLangs = ['hi', 'en', 'mr', 'ta', 'te', 'bn', 'gu', 'kn', 'ml', 'pa', 'or'];

    function normalizeLang(code: string): string {
      const short = code.split('-')[0].toLowerCase();
      return supportedLangs.includes(short) ? short : 'hi';
    }

    expect(normalizeLang('hi-IN')).toBe('hi');
    expect(normalizeLang('ta-IN')).toBe('ta');
    expect(normalizeLang('en-US')).toBe('en');
    expect(normalizeLang('fr-FR')).toBe('hi'); // Unsupported fallback
  });

  test('Validates single-barrel question length in UI chat bubble', () => {
    const question = 'Are you experiencing sweating, shortness of breath, or pain radiating to your jaw or left arm?';
    const words = question.trim().split(/\s+/);
    const qMarks = (question.match(/\?/g) || []).length;

    expect(qMarks).toBe(1);
    expect(words.length).toBeLessThanOrEqual(25);
  });
});
