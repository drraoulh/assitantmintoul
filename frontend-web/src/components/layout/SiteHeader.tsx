'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

import { fetchHealth } from '@/lib/api/client';
import { APP_NAME } from '@/lib/config';
import { useLocale } from '@/lib/i18n';
import type { BackendStatus } from '@/lib/types';

const LINKS = [
  { href: '/explorer', key: 'nav.explorer' },
  { href: '/destinations', key: 'nav.destinations' },
  { href: '/planifier', key: 'nav.planifier' },
  { href: '/hotels', key: 'nav.hotels' },
  { href: '/assistant', key: 'nav.assistant' },
] as const;

export function SiteHeader() {
  const { t, locale, toggleLocale } = useLocale();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<BackendStatus>('checking');

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        await fetchHealth();
        if (!cancelled) setStatus('online');
      } catch {
        if (!cancelled) setStatus('waking');
        try {
          await fetchHealth();
          if (!cancelled) setStatus('online');
        } catch {
          if (!cancelled) setStatus('waking');
        }
      }
    };
    void probe();
    const id = setInterval(() => void probe(), 3 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const statusLabel =
    status === 'online'
      ? t('status.online')
      : status === 'checking'
        ? t('status.checking')
        : t('status.waking');

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-[var(--green-deep)] text-[var(--ivory)]">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 md:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2">
          <span className="text-xl" aria-hidden>
            🇨🇲
          </span>
          <span className="font-display text-lg font-semibold tracking-tight md:text-xl">
            {APP_NAME}
          </span>
        </Link>

        <nav className="ml-4 hidden flex-1 items-center gap-1 lg:flex">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  active
                    ? 'bg-white/15 text-[var(--yellow)]'
                    : 'text-white/85 hover:bg-white/10'
                }`}
              >
                {t(link.key)}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-xs sm:inline-flex">
            <span
              className={`h-2 w-2 rounded-full ${
                status === 'online' ? 'bg-[var(--mint)]' : 'bg-[var(--yellow)]'
              }`}
            />
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={toggleLocale}
            className="rounded-full border border-[var(--yellow)]/70 px-2.5 py-1 text-xs font-bold text-[var(--yellow)]"
            aria-label="Language"
          >
            🌐 {locale.toUpperCase()}
          </button>
          <Link
            href="/mon-voyage"
            className="hidden rounded-full bg-[var(--yellow)] px-3 py-1.5 text-xs font-bold text-[var(--green-deep)] sm:inline-flex"
          >
            {t('nav.trip')}
          </Link>
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/10 lg:hidden"
            aria-label="Menu"
            onClick={() => setOpen((v) => !v)}
          >
            ☰
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-white/10 px-4 py-3 lg:hidden">
          <div className="flex flex-col gap-1">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm hover:bg-white/10"
              >
                {t(link.key)}
              </Link>
            ))}
            <Link
              href="/mon-voyage"
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-2 text-sm hover:bg-white/10"
            >
              {t('nav.trip')}
            </Link>
            <Link
              href="/vision"
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-2 text-sm hover:bg-white/10"
            >
              {t('nav.vision')}
            </Link>
          </div>
        </div>
      ) : null}

      <div className="flex h-1">
        <div className="flex-1 bg-[var(--green)]" />
        <div className="flex-1 bg-[var(--red)]" />
        <div className="flex-1 bg-[var(--yellow)]" />
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-[var(--line)] bg-[var(--ivory)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-[var(--muted)] md:flex-row md:items-center md:justify-between md:px-6">
        <p className="font-display text-[var(--green-deep)]">{APP_NAME}</p>
        <p>Guide touristique intelligent du Cameroun — données vérifiées via l’API SmartMboa.</p>
      </div>
    </footer>
  );
}
