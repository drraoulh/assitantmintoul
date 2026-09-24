'use client';

import { useEffect, useState } from 'react';

import { TourismMap } from '@/components/maps/TourismMap';
import { Button, EmptyState } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { loadTrip } from '@/lib/trip-store';
import type { TripState } from '@/lib/types';

export default function MonVoyagePage() {
  const { t } = useLocale();
  const [trip, setTrip] = useState<TripState | null>(null);

  useEffect(() => {
    setTrip(loadTrip());
  }, []);

  if (!trip) {
    return <div className="mx-auto max-w-6xl px-4 py-12">…</div>;
  }

  const markers = trip.places
    .filter(
      (p) =>
        typeof p.latitude === 'number' &&
        typeof p.longitude === 'number' &&
        Number.isFinite(p.latitude) &&
        Number.isFinite(p.longitude),
    )
    .map((p) => ({
      id: p.id,
      name: p.name,
      latitude: p.latitude as number,
      longitude: p.longitude as number,
      category: p.category,
    }));

  const empty =
    !trip.destination &&
    !trip.places.length &&
    !trip.hotel &&
    !trip.bookings.length &&
    !trip.itineraryText;

  return (
    <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
      <h1 className="font-display text-4xl text-[var(--green-deep)]">{t('trip.title')}</h1>

      {empty ? (
        <div className="mt-8">
          <EmptyState
            title="Votre voyage est vide"
            body="Ajoutez des lieux, créez un itinéraire ou réservez un hébergement de démonstration."
          />
          <div className="mt-4 flex flex-wrap gap-3">
            <Button href="/explorer">Explorer</Button>
            <Button href="/planifier" variant="secondary">
              Planifier
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-8 grid gap-8 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6">
            <section className="rounded-3xl border border-[var(--line)] bg-white p-6">
              <h2 className="font-display text-2xl text-[var(--green-deep)]">Résumé</h2>
              <ul className="mt-3 space-y-1 text-sm">
                <li>Destination : {trip.destination ?? '—'}</li>
                <li>Dates : {trip.dates ?? '—'}</li>
                <li>Voyageurs : {trip.travelers ?? '—'}</li>
                <li>
                  Budget :{' '}
                  {trip.budgetFcfa != null ? `${trip.budgetFcfa} FCFA` : '—'}
                </li>
              </ul>
            </section>

            <section className="rounded-3xl border border-[var(--line)] bg-white p-6">
              <h2 className="font-display text-2xl text-[var(--green-deep)]">Mes lieux</h2>
              <ul className="mt-3 space-y-2">
                {trip.places.map((p) => (
                  <li key={p.id} className="text-sm">
                    {p.name}
                    {p.city ? ` · ${p.city}` : ''}
                  </li>
                ))}
                {!trip.places.length ? (
                  <li className="text-sm text-[var(--muted)]">Aucun lieu ajouté</li>
                ) : null}
              </ul>
            </section>

            {trip.itineraryText ? (
              <section className="rounded-3xl border border-[var(--line)] bg-white p-6">
                <h2 className="font-display text-2xl text-[var(--green-deep)]">Mon itinéraire</h2>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">
                  {trip.itineraryText}
                </p>
              </section>
            ) : null}

            <section className="rounded-3xl border border-[var(--line)] bg-white p-6">
              <h2 className="font-display text-2xl text-[var(--green-deep)]">Mon hôtel</h2>
              <p className="mt-2 text-sm">
                {trip.hotel ? trip.hotel.name : 'Aucun hôtel sélectionné'}
              </p>
            </section>

            <section className="rounded-3xl border border-[var(--line)] bg-white p-6">
              <h2 className="font-display text-2xl text-[var(--green-deep)]">Mes réservations</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {trip.bookings.map((b) => (
                  <li key={b.reference}>
                    <strong>{b.reference}</strong> — {b.hotelName} ({b.checkIn} → {b.checkOut})
                    <span className="ml-2 text-[var(--muted)]">démo</span>
                  </li>
                ))}
                {!trip.bookings.length ? (
                  <li className="text-[var(--muted)]">Aucune réservation</li>
                ) : null}
              </ul>
            </section>
          </div>

          <div>
            <h2 className="mb-3 font-display text-2xl text-[var(--green-deep)]">Ma carte</h2>
            <TourismMap markers={markers} className="h-[28rem]" />
          </div>
        </div>
      )}
    </div>
  );
}
