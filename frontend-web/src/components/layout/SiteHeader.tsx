'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  Compass,
  Hotel,
  Map,
  Menu,
  MessageCircle,
  Plane,
  X,
} from 'lucide-react';

import { fetchHealth } from '@/lib/api/client';
import { APP_NAME } from '@/lib/config';
import { useLocale } from '@/lib/i18n';
import type { BackendStatus } from '@/lib/types';

const LINKS = [
  { href: '/explorer', key: 'nav.explorer', icon: Compass },
  { href: '/planifier', key: 'nav.planifier', icon: Map },
  { href: '/hotels', key: 'nav.hotels', icon: Hotel },
  { href: '/mon-voyage', key: 'nav.trip', icon: Plane },
] as const;

export function SiteHeader() {
  const { t, locale, toggleLocale } = useLocale();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [status, setStatus] = useState<BackendStatus>('checking');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

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
    <header
      className={`sticky top-0 z-40 transition ${
        scrolled
          ? 'border-b border-[var(--line)]/80 bg-[var(--ivory)]/85 text-[var(--ink)] backdrop-blur-md'
          : 'border-b border-transparent bg-[var(--ivory)] text-[var(--ink)]'
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 md:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2" aria-label={APP_NAME}>
          <span
            className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--green-deep)] text-sm text-white"
            aria-hidden
          >
            🇨🇲
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-[var(--green-deep)] md:text-xl">
            {APP_NAME}
          </span>
        </Link>

        <nav className="ml-6 hidden flex-1 items-center gap-1 lg:flex" aria-label="Principal">
          {LINKS.map((link) => {
            const active =
              pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                  active
                    ? 'bg-[var(--mint-soft)] text-[var(--green-deep)] ring-1 ring-[var(--gold)]/40'
                    : 'text-[var(--muted)] hover:bg-[var(--mint-soft)] hover:text-[var(--green-deep)]'
                }`}
              >
                {t(link.key)}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <span
            className="hidden items-center gap-1.5 rounded-full bg-[var(--mint-soft)] px-2.5 py-1 text-xs text-[var(--muted)] sm:inline-flex"
            title={statusLabel}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                status === 'online' ? 'bg-[var(--green-mid)]' : 'bg-[var(--gold)]'
              }`}
              aria-hidden
            />
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={toggleLocale}
            className="rounded-full border border-[var(--line)] px-2.5 py-1 text-xs font-semibold text-[var(--muted)] hover:border-[var(--gold)] hover:text-[var(--green-deep)]"
            aria-label="Changer de langue"
          >
            {locale.toUpperCase()}
          </button>
          <Link
            href="/assistant"
            className="hidden items-center gap-2 rounded-full bg-[var(--green-deep)] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--green)] sm:inline-flex"
          >
            <MessageCircle className="h-4 w-4" aria-hidden />
            Assistant IA
          </Link>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)] lg:hidden"
            aria-label={open ? 'Fermer le menu' : 'Ouvrir le menu'}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-[var(--line)] bg-[var(--ivory)] px-4 py-3 lg:hidden">
          <div className="flex flex-col gap-1">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--mint-soft)]"
              >
                <link.icon className="h-4 w-4 text-[var(--green)]" aria-hidden />
                {t(link.key)}
              </Link>
            ))}
            <Link
              href="/assistant"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--mint-soft)]"
            >
              <MessageCircle className="h-4 w-4 text-[var(--green)]" aria-hidden />
              Assistant IA
            </Link>
            <Link
              href="/culture"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--mint-soft)]"
            >
              Culture
            </Link>
            <Link
              href="/vision"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-[var(--ink)] hover:bg-[var(--mint-soft)]"
            >
              {t('nav.vision')}
            </Link>
            <Link
              href="/?reset_intro=1"
              onClick={() => setOpen(false)}
              className="rounded-xl px-3 py-2 text-xs text-[var(--muted)]"
            >
              Réafficher l&apos;intro
            </Link>
          </div>
        </div>
      ) : null}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-[var(--line)] bg-[var(--green-deep)] text-white">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-[1.2fr_1fr] md:px-6">
        <div>
          <p className="flex items-center gap-2 font-display text-xl font-bold">
            <span aria-hidden>🇨🇲</span> {APP_NAME}
          </p>
          <p className="mt-3 max-w-sm text-sm text-white/75">
            Découvrez le Cameroun autrement.
          </p>
          <Link
            href="/?reset_intro=1"
            className="mt-4 inline-block text-sm text-[var(--gold-soft)] underline-offset-4 hover:underline"
          >
            Revoir l&apos;introduction
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm text-white/80">
          {[
            ['/explorer', 'Explorer'],
            ['/destinations', 'Destinations'],
            ['/culture', 'Culture'],
            ['/planifier', 'Planifier'],
            ['/hotels', 'Hébergements'],
            ['/assistant', 'Assistant IA'],
            ['/mon-voyage', 'Mon voyage'],
            ['/vision', 'Vision'],
          ].map(([href, label]) => (
            <Link key={href} href={href} className="hover:text-[var(--gold)]">
              {label}
            </Link>
          ))}
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-white/55 md:px-6">
        © 2026 {APP_NAME}
      </div>
    </footer>
  );
}
