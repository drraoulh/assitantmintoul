'use client';

import { FormEvent, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { Button, Input } from '@/components/ui';
import { useLocale } from '@/lib/i18n';

export function HomeAssistantTeaser() {
  const { t } = useLocale();
  const router = useRouter();
  const [q, setQ] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  function goAssistant(message?: string) {
    const m = (message ?? q).trim();
    if (m) {
      router.push(`/assistant?q=${encodeURIComponent(m)}`);
    } else {
      router.push('/assistant');
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    goAssistant();
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
      <div className="rounded-[2rem] bg-[var(--green-deep)] px-6 py-10 text-[var(--ivory)] md:px-10">
        <p className="text-sm uppercase tracking-[0.2em] text-[var(--mint)]">
          Assistant IA
        </p>
        <h2 className="mt-2 font-display text-3xl md:text-4xl">
          {t('home.assistantTitle')}
        </h2>
        <p className="mt-3 max-w-xl text-white/80">{t('home.assistantHint')}</p>

        <form
          onSubmit={onSubmit}
          className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center"
        >
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('home.placeholder')}
            className="flex-1 border-0 bg-white/95"
          />
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              aria-label="Voice"
              onClick={() => router.push('/assistant?voice=1')}
            >
              🎙️
            </Button>
            <Button
              type="button"
              variant="ghost"
              aria-label="Vision"
              onClick={() => fileRef.current?.click()}
            >
              📷
            </Button>
            <Button type="submit" variant="primary">
              ➤
            </Button>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={() => router.push('/vision')}
          />
        </form>
      </div>
    </section>
  );
}
