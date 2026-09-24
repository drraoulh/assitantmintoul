'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Search } from 'lucide-react';

import { TourismMap } from '@/components/maps/TourismMap';
import { PlaceCard } from '@/components/places/PlaceCard';
import { PageTransition } from '@/components/motion';
import { EmptyState, ErrorState, Input, Skeleton } from '@/components/ui';
import { friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { isHotelCategory, sitesToMarkers } from '@/lib/utils/response';
import type { TouristSite } from '@/lib/types';

function regionMatches(siteRegion: string, apiRegion: string): boolean {
  return siteRegion.trim().toLowerCase() === apiRegion.trim().toLowerCase();
}

export default function DestinationsInner() {
  const { t } = useLocale();
  const params = useSearchParams();
  const region = params.get('region') ?? undefined;
  const city = params.get('city') ?? undefined;
  const q = params.get('q') ?? '';
  const [items, setItems] = useState<TouristSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState(q);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await listTouristSites(city ? { city } : undefined);
        if (!cancelled) {
          let next = res.items.filter((s) => !isHotelCategory(s.category));
          if (region) {
            next = next.filter((s) => regionMatches(s.region, region));
          }
          setItems(next);
        }
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [region, city]);

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (s) =>
        s.name.toLowerCase().includes(needle) ||
        s.city.toLowerCase().includes(needle) ||
        s.region.toLowerCase().includes(needle) ||
        s.category.toLowerCase().includes(needle),
    );
  }, [items, filter]);

  const markers = sitesToMarkers(filtered);

  return (
    <PageTransition>
      <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
        <h1 className="font-display text-4xl font-bold text-[var(--green-deep)]">
          Destinations
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          {region
            ? `Région : ${region}`
            : city
              ? `Ville : ${city}`
              : 'Lieux touristiques vérifiés'}
        </p>

        <div className="relative mt-6 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
          <Input
            className="pl-10"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrer par nom, ville…"
            aria-label="Filtrer les destinations"
          />
        </div>

        {error ? (
          <div className="mt-6">
            <ErrorState message={error} />
          </div>
        ) : null}

        <div className="mt-8">
          {loading ? (
            <p className="text-sm text-[var(--muted)]">{t('loading.places')}</p>
          ) : (
            <TourismMap markers={markers} className="h-80" />
          )}
        </div>

        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-64" />)
            : filtered.map((site) => <PlaceCard key={site.id} site={site} />)}
        </div>

        {!loading && !filtered.length ? (
          <div className="mt-8">
            <EmptyState title={t('empty.places')} />
          </div>
        ) : null}
      </div>
    </PageTransition>
  );
}
