'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { MapPin, MessageCircle, Plus } from 'lucide-react';

import { TourismMap } from '@/components/maps/TourismMap';
import { PageTransition } from '@/components/motion';
import { Badge, Button, ErrorState, Skeleton } from '@/components/ui';
import { fetchTouristSite, friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { addPlaceToTrip } from '@/lib/trip-store';
import type { TouristSite } from '@/lib/types';

export default function DestinationDetailPage() {
  const params = useParams<{ id: string }>();
  const { t } = useLocale();
  const [site, setSite] = useState<TouristSite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      const rawId = decodeURIComponent(params.id);
      try {
        try {
          const one = await fetchTouristSite(rawId);
          if (!cancelled) setSite(one);
        } catch {
          const all = await listTouristSites();
          const found =
            all.items.find((s) => s.id === rawId) ||
            all.items.find((s) => s.slug === rawId) ||
            all.items.find((s) => s.name.toLowerCase() === rawId.toLowerCase()) ||
            all.items.find((s) => s.name.toLowerCase().includes(rawId.toLowerCase()));
          if (!found) throw new Error('not found');
          if (!cancelled) setSite(found);
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
  }, [params.id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 px-4 py-12 md:px-6">
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (error || !site) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
        <ErrorState message={error ?? t('empty.places')} />
      </div>
    );
  }

  const markers =
    typeof site.latitude === 'number' && typeof site.longitude === 'number'
      ? [
          {
            id: site.id,
            name: site.name,
            latitude: site.latitude,
            longitude: site.longitude,
            category: site.category,
          },
        ]
      : [];

  return (
    <PageTransition>
      <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
        <div className="relative overflow-hidden rounded-[1.5rem]">
          {site.images[0] ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={site.images[0]}
              alt={site.name}
              className="h-72 w-full object-cover md:h-[28rem]"
            />
          ) : (
            <div className="flex h-72 items-end bg-gradient-to-br from-[var(--green-deep)] via-[var(--green)] to-[var(--gold)]/40 p-8 md:h-96">
              <h1 className="font-display text-4xl font-bold text-white md:text-5xl">
                {site.name}
              </h1>
            </div>
          )}
          {site.images[0] ? (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/50 to-transparent" />
          ) : null}
        </div>

        <div className="mt-8 grid gap-10 lg:grid-cols-[1.4fr_1fr]">
          <div>
            {site.images[0] ? (
              <h1 className="font-display text-4xl font-bold text-[var(--green-deep)]">
                {site.name}
              </h1>
            ) : null}
            <p className="mt-2 flex items-center gap-1 text-[var(--muted)]">
              <MapPin className="h-4 w-4" aria-hidden />
              {site.city}, {site.region}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge>{site.category}</Badge>
              {site.price ? <Badge tone="gold">{site.price}</Badge> : null}
            </div>
            <p className="mt-6 whitespace-pre-wrap leading-relaxed text-[var(--ink)]">
              {site.description}
            </p>
            {site.culture ? (
              <section className="mt-8">
                <h2 className="font-display text-2xl font-semibold text-[var(--green-deep)]">
                  Culture
                </h2>
                <p className="mt-2 text-[var(--ink)]">{site.culture}</p>
              </section>
            ) : null}
            {site.history ? (
              <section className="mt-8">
                <h2 className="font-display text-2xl font-semibold text-[var(--green-deep)]">
                  Histoire
                </h2>
                <p className="mt-2 text-[var(--ink)]">{site.history}</p>
              </section>
            ) : null}
            {site.activities?.length ? (
              <section className="mt-8">
                <h2 className="font-display text-2xl font-semibold text-[var(--green-deep)]">
                  Activités
                </h2>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {site.activities.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </section>
            ) : null}
            {site.sources?.length ? (
              <section className="mt-8">
                <h2 className="font-display text-2xl font-semibold text-[var(--green-deep)]">
                  {t('sources.title')}
                </h2>
                <ul className="mt-2 space-y-1 text-sm">
                  {site.sources.map((s, i) => (
                    <li key={`${s.title}-${i}`}>
                      {s.url ? (
                        <a
                          href={s.url}
                          className="text-[var(--green)] underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {s.title}
                        </a>
                      ) : (
                        s.title
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            <div className="mt-8 flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={() => {
                  addPlaceToTrip({
                    id: site.id,
                    name: site.name,
                    city: site.city,
                    region: site.region,
                    category: site.category,
                    imageUrl: site.images[0],
                    latitude: site.latitude,
                    longitude: site.longitude,
                  });
                  setAdded(true);
                }}
              >
                <Plus className="h-4 w-4" aria-hidden />
                {added ? t('place.added') : t('place.add')}
              </Button>
              <Button
                href={`/assistant?q=${encodeURIComponent(`Parle-moi de ${site.name}`)}`}
                variant="outline"
              >
                <MessageCircle className="h-4 w-4" aria-hidden />
                Demander à SmartMboa
              </Button>
              <Button
                href={`/destinations?region=${encodeURIComponent(site.region)}`}
                variant="secondary"
              >
                Voir autour de ce lieu
              </Button>
            </div>
          </div>
          <div className="space-y-4">
            {site.opening_hours ? (
              <div className="rounded-2xl border border-[var(--line)] bg-white p-4 text-sm">
                <strong>Horaires</strong>
                <p className="mt-1 text-[var(--muted)]">{site.opening_hours}</p>
              </div>
            ) : null}
            <TourismMap markers={markers} className="h-80" />
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
