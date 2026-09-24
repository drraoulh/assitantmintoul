'use client';

import Image from 'next/image';
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

/** Prefer scenic photos over Ayila'a /logos/ branding assets when picking a cover. */
function pickRegionCover(images: (string | undefined)[]): string | undefined {
  const urls = images.filter((u): u is string => Boolean(u?.trim()));
  if (!urls.length) return undefined;
  const scenic = urls.find((u) => !u.toLowerCase().includes('/logos/'));
  return scenic ?? urls[0];
}

export default function ExplorerPage() {
  const { t, locale } = useLocale();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [covers, setCovers] = useState<Record<string, string>>({});
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
        const nextCounts: Record<string, number> = {};
        const nextCovers: Record<string, string> = {};
        for (const r of REGIONS) {
          const regionSites = res.items.filter((s) =>
            regionMatches(s.region, r.apiRegion),
          );
          nextCounts[r.id] = regionSites.length;
          const cover = pickRegionCover(regionSites.map((s) => s.images?.[0]));
          if (cover) nextCovers[r.id] = cover;
        }
        setCounts(nextCounts);
        setCovers(nextCovers);
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
              const cover = covers[r.id];
              const name = locale === 'fr' ? r.nameFr : r.nameEn;
              const capital = locale === 'fr' ? r.capitalFr : r.capitalEn;
              return (
                <article
                  key={r.id}
                  className="flex flex-col justify-between rounded-3xl border border-[var(--line)] bg-white p-6 shadow-sm"
                >
                  <div>
                    <div className="relative h-28 overflow-hidden rounded-2xl bg-gradient-to-br from-[var(--green-deep)] via-[var(--green)] to-[var(--yellow)]/50">
                      {cover ? (
                        <Image
                          src={cover}
                          alt={name}
                          fill
                          className="object-cover"
                          sizes="(max-width:768px) 100vw, 33vw"
                          unoptimized
                        />
                      ) : null}
                    </div>
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
