import { AbhaProfile } from '@/types/abha';

export function normalizeAbhaNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  if (digits.length === 14) {
    return `${digits.slice(0, 2)}-${digits.slice(2, 6)}-${digits.slice(6, 10)}-${digits.slice(10, 14)}`;
  }
  return raw.trim();
}

export function parseAbhaQrPayload(rawScannedText: string): AbhaProfile | null {
  if (!rawScannedText || !rawScannedText.trim()) return null;
  const text = rawScannedText.trim();

  try {
    const data = JSON.parse(text);
    if (typeof data === 'object' && data !== null) {
      const rawNum = data.hidn || data.abha_number || data.id || '';
      return {
        abhaNumber: rawNum ? normalizeAbhaNumber(String(rawNum)) : '91-0000-0000-0000',
        abhaAddress: data.hid || data.abha_address,
        name: data.name,
        gender: data.gender,
        dob: data.dob,
        mobile: data.mobile,
      };
    }
  } catch {
    // Continue
  }

  if (text.startsWith('http://') || text.startsWith('https://')) {
    try {
      const url = new URL(text);
      const rawNum = url.searchParams.get('hidn') || url.searchParams.get('id') || '';
      return {
        abhaNumber: rawNum ? normalizeAbhaNumber(rawNum) : '91-0000-0000-0000',
        abhaAddress: url.searchParams.get('hid') || undefined,
        name: url.searchParams.get('name') || undefined,
      };
    } catch {
      // Continue
    }
  }

  const match = text.match(/\b\d{2}-\d{4}-\d{4}-\d{4}\b/) || text.match(/\b\d{14}\b/);
  if (match) {
    return { abhaNumber: normalizeAbhaNumber(match[0]) };
  }

  return { abhaNumber: text.slice(0, 17) };
}
