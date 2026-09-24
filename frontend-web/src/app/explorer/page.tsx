'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Badge, Button, EmptyState, ErrorState, Skeleton } from '@/components/ui';
import { friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { REGIONS } from '@/lib/regions';

function regionMatches(siteRegion: string, apiRegion: string): boolean {
  // Exact equality only — avoid "Ouest" matching "Nord-Ouest" / "Sud-Ouest".
  return siteRegion.trim().toLowerCase() === apiRegion.trim().toLowerCase();
}

export default function ExplorerPage() {
  const { t, locale } = useLocale();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await listTouristSites();
        if (cancelled) return;
        const next: Record<string, number> = {};
        for (const r of REGIONS) {
          next[r.id] = res.items.filter((s) => regionMatches(s.region, r.apiRegion)).length;
        }
        setCounts(next);
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <h1 className="font-display text-4xl text-[var(--green-deep)] md:text-5xl">
        {t('explorer.title')}
      </h1>
      <p className="mt-3 max-w-2xl text-[var(--muted)]">{t('explorer.sub')}</p>

      {error ? (
        <div className="mt-6">
          <ErrorState message={error} />
        </div>
      ) : null}

      <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))
          : REGIONS.map((r) => {
              const count = counts[r.id] ?? 0;
              const name = locale === 'fr' ? r.nameFr : r.nameEn;
              const capital = locale === 'fr' ? r.capitalFr : r.capitalEn;
              return (
                <article
                  key={r.id}
                  className="flex flex-col justify-between rounded-3xl border border-[var(--line)] bg-white p-6 shadow-sm"
                >
                  <div>
                    <div className="h-28 rounded-2xl bg-gradient-to-br from-[var(--green-deep)] via-[var(--green)] to-[var(--yellow)]/50" />
                    <h2 className="mt-4 font-display text-2xl text-[var(--green-deep)]">
                      {name}
                    </h2>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {t('explorer.capital')} : {capital}
                    </p>
                    <div className="mt-3">
                      <Badge tone="yellow">
                        {count} {t('explorer.count')}
                      </Badge>
                    </div>
                  </div>
                  <div className="mt-5">
                    <Button href={`/destinations?region=${encodeURIComponent(r.apiRegion)}`}>
                      {t('explorer.cta')}
                    </Button>
                  </div>
                </article>
              );
            })}
      </div>

      {!loading && Object.values(counts).every((c) => c === 0) ? (
        <div className="mt-8">
          <EmptyState
            title={t('empty.places')}
            body="Le serveur API est peut-être en réveil (Render free)."
          />
        </div>
      ) : null}

      <p className="mt-10 text-sm text-[var(--muted)]">
        Voir aussi{' '}
        <Link href="/destinations" className="text-[var(--green)] underline">
          toutes les destinations
        </Link>
        .
      </p>
    </div>
  );
}
