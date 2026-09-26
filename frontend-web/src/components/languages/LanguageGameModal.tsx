'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Languages, RotateCcw, X } from 'lucide-react';

import {
  languageMeta,
  languagePacks,
  pickQuestions,
  type QuizPack,
  type QuizQuestion,
} from '@/lib/languages/games';
import { useLocale } from '@/lib/i18n';

type Step = 'pick' | 'quiz' | 'done';

type Props = {
  open: boolean;
  onClose: () => void;
};

const PACK_IDS = ['ewondo', 'duala', 'fulfulde', 'yemba', 'mix'] as const;

export function LanguageGameModal({ open, onClose }: Props) {
  const { locale } = useLocale();
  const fr = locale === 'fr';
  const [step, setStep] = useState<Step>('pick');
  const [packId, setPackId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [revealed, setRevealed] = useState(false);

  const reset = useCallback(() => {
    setStep('pick');
    setPackId(null);
    setQuestions([]);
    setIndex(0);
    setSelected(null);
    setScore(0);
    setRevealed(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    reset();
  }, [open, reset]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  const packTitle = useMemo(() => {
    const meta = languageMeta.find((m) => m.id === packId);
    if (!meta) return '';
    return fr ? meta.titleFr : meta.titleEn;
  }, [packId, fr]);

  function startPack(id: string) {
    let pool: QuizQuestion[] = [];
    if (id === 'mix') {
      pool = languagePacks.flatMap((p) => p.questions);
    } else {
      const pack: QuizPack | undefined = languagePacks.find((p) => p.id === id);
      pool = pack?.questions ?? [];
    }
    setPackId(id);
    setQuestions(pickQuestions(pool, 6));
    setIndex(0);
    setSelected(null);
    setScore(0);
    setRevealed(false);
    setStep('quiz');
  }

  function answer(optionId: string) {
    if (revealed) return;
    const q = questions[index];
    if (!q) return;
    setSelected(optionId);
    setRevealed(true);
    if (optionId === q.correctId) setScore((s) => s + 1);
  }

  function next() {
    if (index + 1 >= questions.length) {
      setStep('done');
      return;
    }
    setIndex((i) => i + 1);
    setSelected(null);
    setRevealed(false);
  }

  if (!open) return null;

  const q = questions[index];

  return (
    <div
      className="fixed inset-0 z-[80] flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="lang-game-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl">
        <header className="flex shrink-0 items-center gap-3 border-b border-gray-100 px-4 py-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FCD116]/35">
            <Languages className="h-5 w-5 text-[#007A5E]" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <h2 id="lang-game-title" className="truncate text-base font-bold text-[#007A5E]">
              {fr ? 'Parler local' : 'Speak local'}
            </h2>
            <p className="truncate text-xs text-[#535557]">
              {step === 'pick'
                ? fr
                  ? 'Apprenez les langues du Cameroun'
                  : 'Learn Cameroon’s local languages'
                : packTitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={fr ? 'Fermer' : 'Close'}
            className="rounded-full p-2 text-gray-500 hover:bg-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
          {step === 'pick' ? (
            <div className="space-y-3">
              <p className="text-sm text-[#535557]">
                {fr
                  ? 'Choisissez une langue — 6 questions, réponses immédiates.'
                  : 'Pick a language — 6 questions with instant feedback.'}
              </p>
              <div className="grid gap-3">
                {PACK_IDS.map((id) => {
                  const meta = languageMeta.find((m) => m.id === id)!;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => startPack(id)}
                      className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 text-left transition hover:border-[#007A5E] hover:bg-[#e7f6f1]"
                    >
                      <span>
                        <span className="block font-bold text-[#007A5E]">
                          {fr ? meta.titleFr : meta.titleEn}
                        </span>
                        <span className="text-xs text-[#535557]">
                          {fr ? meta.tagFr : meta.tagEn}
                        </span>
                      </span>
                      <span className="rounded-full bg-[#CE1126]/10 px-2.5 py-1 text-xs font-semibold text-[#CE1126]">
                        Quiz
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          {step === 'quiz' && q ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs font-semibold text-[#535557]">
                <span>
                  {fr ? 'Question' : 'Question'} {index + 1}/{questions.length}
                </span>
                <span className="rounded-full bg-[#007A5E]/10 px-2 py-0.5 text-[#007A5E]">
                  {score} {fr ? 'bonnes' : 'correct'}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-[#FCD116] transition-all"
                  style={{ width: `${((index + (revealed ? 1 : 0)) / questions.length) * 100}%` }}
                />
              </div>
              <div>
                <p className="text-base font-semibold text-gray-900">
                  {fr ? q.promptFr : q.promptEn}
                </p>
                {q.highlight ? (
                  <p className="mt-2 inline-block rounded-lg bg-[#FCD116]/30 px-3 py-1.5 text-lg font-bold text-[#007A5E]">
                    {q.highlight}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                {q.options.map((opt) => {
                  const isCorrect = opt.id === q.correctId;
                  const isPick = selected === opt.id;
                  let ring = 'border-gray-200 hover:border-[#007A5E]';
                  if (revealed && isCorrect) ring = 'border-[#007A5E] bg-[#e7f6f1]';
                  else if (revealed && isPick && !isCorrect) ring = 'border-[#CE1126] bg-[#fff6f6]';
                  else if (isPick) ring = 'border-[#007A5E] bg-[#e7f6f1]';
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      disabled={revealed}
                      onClick={() => answer(opt.id)}
                      className={`rounded-xl border px-4 py-3 text-left text-sm font-medium text-gray-800 transition ${ring} disabled:cursor-default`}
                    >
                      {fr ? opt.labelFr : opt.labelEn}
                    </button>
                  );
                })}
              </div>
              {revealed ? (
                <div className="rounded-xl bg-gray-50 p-3 text-sm text-[#535557]">
                  <p className="mb-1 flex items-center gap-1.5 font-semibold text-[#007A5E]">
                    <Check className="h-4 w-4" aria-hidden />
                    {fr ? 'Explication' : 'Explanation'}
                  </p>
                  {fr ? q.explainFr : q.explainEn}
                </div>
              ) : null}
            </div>
          ) : null}

          {step === 'done' ? (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#FCD116]/40 text-2xl font-bold text-[#007A5E]">
                {score}/{questions.length}
              </div>
              <h3 className="text-xl font-bold text-[#007A5E]">
                {score >= questions.length - 1
                  ? fr
                    ? 'Excellent !'
                    : 'Excellent!'
                  : score >= Math.ceil(questions.length / 2)
                    ? fr
                      ? 'Bien joué'
                      : 'Well done'
                    : fr
                      ? 'Continuez à pratiquer'
                      : 'Keep practising'}
              </h3>
              <p className="text-sm text-[#535557]">
                {fr
                  ? `Vous avez ${score} bonne${score > 1 ? 's' : ''} réponse${score > 1 ? 's' : ''} sur ${questions.length} en ${packTitle}.`
                  : `You got ${score} out of ${questions.length} right in ${packTitle}.`}
              </p>
            </div>
          ) : null}
        </div>

        <footer className="shrink-0 border-t border-gray-100 px-4 py-3">
          {step === 'quiz' && revealed ? (
            <button
              type="button"
              onClick={next}
              className="w-full rounded-full bg-[#007A5E] py-3 text-sm font-bold text-white hover:bg-[#00614b]"
            >
              {index + 1 >= questions.length
                ? fr
                  ? 'Voir le score'
                  : 'See score'
                : fr
                  ? 'Question suivante'
                  : 'Next question'}
            </button>
          ) : null}
          {step === 'done' ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={reset}
                className="flex flex-1 items-center justify-center gap-2 rounded-full border border-gray-200 py-3 text-sm font-bold text-[#007A5E] hover:bg-gray-50"
              >
                <RotateCcw className="h-4 w-4" aria-hidden />
                {fr ? 'Rejouer' : 'Play again'}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-full bg-[#007A5E] py-3 text-sm font-bold text-white hover:bg-[#00614b]"
              >
                {fr ? 'Fermer' : 'Close'}
              </button>
            </div>
          ) : null}
          {step === 'pick' ? (
            <p className="text-center text-xs text-[#535557]">
              {fr
                ? 'Ewondo · Duala · Fulfulde · Yemba'
                : 'Ewondo · Duala · Fulfulde · Yemba'}
            </p>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
