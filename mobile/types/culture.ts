export interface Expression {
  id: string;
  language: string;
  phrase: string;
  translationFr: string;
  translationEn: string;
  pronunciation: string;
  contextFr: string;
  contextEn: string;
  /** Optional bundled audio (require id). */
  audio?: number;
}
