export interface AbhaProfile {
  abhaNumber: string;
  abhaAddress?: string;
  name?: string;
  gender?: 'M' | 'F' | 'O' | string;
  age?: number;
  dob?: string;
  mobile?: string;
  photoUrl?: string;
  prakriti?: string;
  recordsCount?: number;
  documentsCount?: number;
}
