'use client';

import { FormEvent, Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import { Button, ErrorState, Input, Skeleton } from '@/components/ui';
import { fetchTouristSite, friendlyError, listTouristSites } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { addBooking, makeBookingRef, setTripHotel } from '@/lib/trip-store';
import type { TouristSite } from '@/lib/types';

function BookingForm() {
  const { t } = useLocale();
  const params = useSearchParams();
  const hotelId = params.get('hotel');
  const [hotel, setHotel] = useState<TouristSite | null>(null);
  const [step, setStep] = useState(0);
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');
  const [guests, setGuests] = useState('2');
  const [room, setRoom] = useState('Standard');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [ref, setRef] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!hotelId) return;
      try {
        try {
          const one = await fetchTouristSite(hotelId);
          if (!cancelled) setHotel(one);
        } catch {
          const all = await listTouristSites();
          const found = all.items.find((s) => s.id === hotelId);
          if (!cancelled) setHotel(found ?? null);
        }
      } catch (e) {
        if (!cancelled) setError(friendlyError(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hotelId]);

  function onConfirm(e: FormEvent) {
    e.preventDefault();
    if (!hotel) return;
    const reference = makeBookingRef();
    setTripHotel({
      id: hotel.id,
      name: hotel.name,
      city: hotel.city,
      region: hotel.region,
      category: hotel.category,
    });
    addBooking({
      reference,
      hotelName: hotel.name,
      hotelId: hotel.id,
      checkIn,
      checkOut,
      guests: Number(guests) || 1,
      guestName: name,
      guestEmail: email,
      createdAt: new Date().toISOString(),
      demo: true,
    });
    setRef(reference);
    setStep(6);
  }

  if (ref) {
    return (
      <div className="rounded-3xl border border-[var(--line)] bg-white p-8 text-center">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--green)]">
          {t('booking.demoNote')}
        </p>
        <h2 className="mt-3 font-display text-3xl text-[var(--green-deep)]">
          {t('booking.done')}
        </h2>
        <p className="mt-4 text-lg">
          Référence : <strong>{ref}</strong>
        </p>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Confirmation de démonstration (aucun email réel — le backend n’expose pas encore d’envoi mail).
        </p>
        <div className="mt-6">
          <Button href="/mon-voyage">Mon voyage</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-[var(--line)] bg-white p-6 md:p-8">
      <p className="text-sm font-semibold text-[var(--yellow-ink,#7A5D00)] bg-[var(--yellow)]/40 inline-block rounded-full px-3 py-1">
        {t('booking.demoNote')}
      </p>
      <h1 className="mt-4 font-display text-3xl text-[var(--green-deep)]">{t('booking.title')}</h1>
      {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}
      {hotel ? (
        <p className="mt-2 text-[var(--muted)]">
          {hotel.name} · {hotel.city}
        </p>
      ) : (
        <p className="mt-2 text-sm text-[var(--muted)]">
          Sélectionnez un hôtel depuis <a className="underline" href="/hotels">Hébergements</a>.
        </p>
      )}

      <ol className="mt-6 flex flex-wrap gap-2 text-xs">
        {['Hôtel', 'Dates', 'Voyageurs', 'Chambre', 'Coordonnées', 'Résumé'].map((label, i) => (
          <li
            key={label}
            className={`rounded-full px-3 py-1 ${
              step === i ? 'bg-[var(--green)] text-white' : 'bg-[var(--line)] text-[var(--muted)]'
            }`}
          >
            {label}
          </li>
        ))}
      </ol>

      <form onSubmit={onConfirm} className="mt-8 space-y-4">
        {step === 0 && (
          <Button type="button" disabled={!hotel} onClick={() => setStep(1)}>
            Continuer
          </Button>
        )}
        {step === 1 && (
          <>
            <Input type="date" value={checkIn} onChange={(e) => setCheckIn(e.target.value)} required />
            <Input type="date" value={checkOut} onChange={(e) => setCheckOut(e.target.value)} required />
            <Button type="button" onClick={() => setStep(2)}>
              Continuer
            </Button>
          </>
        )}
        {step === 2 && (
          <>
            <Input value={guests} onChange={(e) => setGuests(e.target.value)} required />
            <Button type="button" onClick={() => setStep(3)}>
              Continuer
            </Button>
          </>
        )}
        {step === 3 && (
          <>
            <Input value={room} onChange={(e) => setRoom(e.target.value)} />
            <Button type="button" onClick={() => setStep(4)}>
              Continuer
            </Button>
          </>
        )}
        {step === 4 && (
          <>
            <Input placeholder="Nom" value={name} onChange={(e) => setName(e.target.value)} required />
            <Input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="button" onClick={() => setStep(5)}>
              Continuer
            </Button>
          </>
        )}
        {step === 5 && (
          <>
            <div className="rounded-xl bg-[var(--sand)] p-4 text-sm">
              <p>
                <strong>{hotel?.name}</strong>
              </p>
              <p>
                {checkIn} → {checkOut}
              </p>
              <p>
                {guests} voyageurs · {room}
              </p>
              <p>
                {name} · {email}
              </p>
            </div>
            <Button type="submit">{t('booking.confirm')}</Button>
          </>
        )}
      </form>
    </div>
  );
}

export default function BookingPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12 md:px-6">
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <BookingForm />
      </Suspense>
    </div>
  );
}
