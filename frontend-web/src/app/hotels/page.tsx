'use client';

import { MapPin } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Badge, Button, EmptyState, ErrorState, Skeleton } from '@/components/ui';
import { friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { setTripHotel } from '@/lib/trip-store';
import { isHotelCategory } from '@/lib/utils/response';
import type { TouristSite } from '@/lib/types';

export default function HotelsPage() {
  const { t } = useLocale();
  const [hotels, setHotels] = useState<TouristSite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await listTouristSites();
        if (!cancelled) {
          setHotels(res.items.filter((s) => isHotelCategory(s.category)));
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
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <h1 className="font-display text-4xl text-[var(--green-deep)]">{t('hotels.title')}</h1>
      <p className="mt-2 text-[var(--muted)]">
        Uniquement les hébergements présents dans la base (ex. Ayila’a). {t('hotels.demo')}.
      </p>

      {error ? <div className="mt-6"><ErrorState message={error} /></div> : null}

      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-64" />)
          : hotels.map((h) => (
              <article
                key={h.id}
                className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-sm"
              >
                <div className="h-40 bg-gradient-to-br from-[var(--green-deep)] to-[var(--green-mid)]" />
                <div className="space-y-3 p-5">
                  <h2 className="font-display text-xl text-[var(--green-deep)]">{h.name}</h2>
                  <p className="flex items-start gap-1.5 text-sm text-[var(--muted)]">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span>
                      {h.city}, {h.region}
                    </span>
                  </p>
                  {h.price ? (
                    <Badge tone="yellow">
                      {t('hotels.indicative')} : {h.price}
                    </Badge>
                  ) : (
                    <Badge tone="muted">{t('hotels.indicative')}</Badge>
                  )}
                  <p className="line-clamp-3 text-sm text-[var(--ink)]">{h.description}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button href={`/destinations/${encodeURIComponent(h.id)}`} size="sm" variant="secondary">
                      Détails
                    </Button>
                    <Button
                      size="sm"
                      type="button"
                      onClick={() => {
                        setTripHotel({
                          id: h.id,
                          name: h.name,
                          city: h.city,
                          region: h.region,
                          category: h.category,
                          latitude: h.latitude,
                          longitude: h.longitude,
                        });
                        window.location.href = `/booking?hotel=${encodeURIComponent(h.id)}`;
                      }}
                    >
                      Réserver
                    </Button>
                  </div>
                </div>
              </article>
            ))}
      </div>

      {!loading && !hotels.length ? (
        <div className="mt-8">
          <EmptyState
            title="Aucun hôtel listé dans la catalogue filtrée"
            body="Demandez un hébergement à l’assistant — seuls les établissements vérifiés (ex. Ayila’a) seront proposés."
          />
          <div className="mt-4">
            <Link href="/assistant?q=Propose-moi%20un%20h%C3%B4tel%20v%C3%A9rifi%C3%A9%20%C3%A0%20Bafoussam" className="text-[var(--green)] underline">
              Demander à l’assistant
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
