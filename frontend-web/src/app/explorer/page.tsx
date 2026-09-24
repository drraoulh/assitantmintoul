'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Map as MapIcon, Search } from 'lucide-react';

import { TourismMap } from '@/components/maps/TourismMap';
import { PlaceCard } from '@/components/places/PlaceCard';
import { RegionCoverCard } from '@/components/places/RegionCoverCard';
import { PageTransition, SlideUp } from '@/components/motion';
import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  Select,
  Skeleton,
} from '@/components/ui';
import { friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { REGIONS } from '@/lib/regions';
import { isHotelCategory, sitesToMarkers } from '@/lib/utils/response';
import type { TouristSite } from '@/lib/types';

function regionMatches(siteRegion: string, apiRegion: string): boolean {
  return siteRegion.trim().toLowerCase() === apiRegion.trim().toLowerCase();
}

const CATEGORY_FILTERS = [
  { id: 'all', label: 'Tous' },
  { id: 'nature', label: 'Nature' },
  { id: 'culture', label: 'Culture' },
  { id: 'heritage', label: 'Patrimoine' },
  { id: 'activity', label: 'Activités' },
  { id: 'beach', label: 'Plages' },
  { id: 'park', label: 'Parcs' },
] as const;

export default function ExplorerPage() {
  const { t, locale } = useLocale();
  const [sites, setSites] = useState<TouristSite[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('');
  const [category, setCategory] = useState('all');
  const [showMap, setShowMap] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await listTouristSites();
        if (cancelled) return;
        const items = res.items.filter((s) => !isHotelCategory(s.category));
        setSites(items);
        const next: Record<string, number> = {};
        for (const r of REGIONS) {
          next[r.id] = items.filter((s) => regionMatches(s.region, r.apiRegion)).length;
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

  const filtered = useMemo(() => {
    let next = sites;
    if (region) {
      next = next.filter((s) => regionMatches(s.region, region));
    }
    if (category !== 'all') {
      next = next.filter((s) => s.category.toLowerCase().includes(category));
    }
    const needle = query.trim().toLowerCase();
    if (needle) {
      next = next.filter(
        (s) =>
          s.name.toLowerCase().includes(needle) ||
          s.city.toLowerCase().includes(needle) ||
          s.region.toLowerCase().includes(needle),
      );
    }
    return next;
  }, [sites, region, category, query]);

  const markers = sitesToMarkers(filtered);

  return (
    <PageTransition>
      <div className="mx-auto max-w-6xl px-4 py-10 md:px-6 md:py-12">
        <SlideUp>
          <h1 className="font-display text-4xl font-bold text-[var(--green-deep)]">
            Explorez le Cameroun
          </h1>
          <p className="mt-3 max-w-2xl text-[var(--muted)]">{t('explorer.sub')}</p>
        </SlideUp>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]" />
            <Input
              className="pl-10"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher une destination…"
              aria-label="Rechercher une destination"
            />
          </div>
          <Select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            aria-label="Région"
            className="sm:w-48"
          >
            <option value="">Toutes les régions</option>
            {REGIONS.map((r) => (
              <option key={r.id} value={r.apiRegion}>
                {locale === 'fr' ? r.nameFr : r.nameEn}
              </option>
            ))}
          </Select>
        </div>

        <div className="mt-4 flex gap-2 overflow-x-auto no-scrollbar pb-1">
          {CATEGORY_FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setCategory(f.id)}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                category === f.id
                  ? 'bg-[var(--green-deep)] text-white'
                  : 'border border-[var(--line)] bg-white text-[var(--muted)] hover:border-[var(--gold)]'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error ? (
          <div className="mt-6">
            <ErrorState message={error} />
          </div>
        ) : null}

        <h2 className="mt-10 font-display text-2xl font-semibold text-[var(--green-deep)]">
          Les 10 régions
        </h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {loading
            ? Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="aspect-[5/3] w-full" />
              ))
            : REGIONS.map((r) => (
                <RegionCoverCard
                  key={r.id}
                  region={r}
                  count={counts[r.id]}
                  locale={locale}
                  active={region === r.apiRegion}
                  onClick={() =>
                    setRegion((prev) => (prev === r.apiRegion ? '' : r.apiRegion))
                  }
                />
              ))}
        </div>

        <div className="mt-10 flex items-center justify-between gap-3">
          <h2 className="font-display text-2xl font-semibold text-[var(--green-deep)]">
            Lieux {region ? `· ${region}` : ''}
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="lg:hidden"
            onClick={() => setShowMap((v) => !v)}
          >
            <MapIcon className="h-4 w-4" aria-hidden />
            {showMap ? 'Masquer la carte' : 'Voir la carte'}
          </Button>
        </div>

        <div className="mt-6 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="grid gap-5 sm:grid-cols-2">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-64 w-full" />
                ))
              : filtered.map((site) => <PlaceCard key={site.id} site={site} />)}
            {!loading && !filtered.length ? (
              <div className="sm:col-span-2">
                <EmptyState title={t('empty.places')} />
              </div>
            ) : null}
          </div>
          <div className={`${showMap ? 'block' : 'hidden'} lg:block`}>
            <div className="sticky top-24">
              <TourismMap markers={markers} className="h-[28rem]" />
            </div>
          </div>
        </div>

        <p className="mt-10 text-sm text-[var(--muted)]">
          Voir aussi{' '}
          <Link href="/destinations" className="text-[var(--green)] underline">
            toutes les destinations
          </Link>{' '}
          ·{' '}
          <Link href="/culture" className="text-[var(--green)] underline">
            culture &amp; histoire
          </Link>
          .
        </p>
      </div>
    </PageTransition>
  );
}
