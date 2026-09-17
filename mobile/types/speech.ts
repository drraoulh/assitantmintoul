export interface TranscriptionResponse {
  text: string;
  language?: string | null;
  provider: string;
}
