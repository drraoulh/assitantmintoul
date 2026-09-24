'use client';

import Link from 'next/link';
import { Calendar, Hotel, MapPin, Plus } from 'lucide-react';

import { PlaceCard } from '@/components/places/PlaceCard';
import { TourismMap } from '@/components/maps/TourismMap';
import { Badge, Button } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { addPlaceToTrip } from '@/lib/trip-store';
import type {
  ChatBudget,
  ChatHotel,
  ChatItinerary,
  ChatPlace,
  ChatSource,
  ChatVisionPayload,
  MapMarker,
  ResponseKind,
} from '@/lib/types';

export function ResponseRenderer({
  text,
  kind,
  sources,
  markers,
  places,
  itinerary,
  budget,
  hotels,
  vision,
}: {
  text: string;
  kind: ResponseKind;
  sources?: ChatSource[];
  markers?: MapMarker[];
  places?: ChatPlace[] | null;
  itinerary?: ChatItinerary | null;
  budget?: ChatBudget | null;
  hotels?: ChatHotel[] | null;
  vision?: ChatVisionPayload | null;
}) {
  const { t } = useLocale();
  const placeList =
    places && places.length > 0
      ? places
      : undefined;
  const showPlaceCards =
    (kind === 'PLACE_LIST' ||
      kind === 'PLACE_SEARCH' ||
      kind === 'PLACE_DETAILS') &&
    Boolean(placeList || (sources && sources.length > 0));

  const hotelList =
    hotels && hotels.length > 0
      ? hotels
      : kind === 'HOTEL' && placeList
        ? placeList
        : null;

  return (
    <div className="space-y-5">
      <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--ink)]">
        {text}
      </div>

      {vision?.description ? (
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--mint-soft)]/60 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--green)]">
            Identification
          </p>
          <p className="mt-2 text-sm">{vision.description}</p>
        </div>
      ) : null}

      {showPlaceCards && placeList ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {placeList.map((p) => (
            <PlaceCard key={p.id} site={p} />
          ))}
        </div>
      ) : null}

      {showPlaceCards && !placeList && sources?.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sources.map((s, i) => (
            <PlaceCard
              key={`${s.title}-${i}`}
              site={{
                id: encodeURIComponent(s.title),
                name: s.title,
                city: s.city,
                region: s.region,
                category: s.category,
                image_url: s.image_url,
              }}
              href={
                s.url?.startsWith('http')
                  ? undefined
                  : `/destinations?q=${encodeURIComponent(s.title)}`
              }
            />
          ))}
        </div>
      ) : null}

      {kind === 'ITINERARY' || kind === 'BUDGET_TRIP' || itinerary ? (
        <ItineraryCard itinerary={itinerary} fallbackText={null} />
      ) : null}

      {budget ? <BudgetCardFromApi budget={budget} /> : null}

      {hotelList && hotelList.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm font-semibold text-[var(--green-deep)]">Hébergements</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {hotelList.map((h, i) => (
              <HotelMiniCard key={('id' in h && h.id) || `${h.name}-${i}`} hotel={h} />
            ))}
          </div>
        </div>
      ) : null}

      {markers && markers.length > 0 ? (
        <TourismMap markers={markers} className="h-72" />
      ) : null}

      {placeList && placeList.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              for (const p of placeList) {
                addPlaceToTrip({
                  id: p.id,
                  name: p.name,
                  city: p.city ?? undefined,
                  region: p.region ?? undefined,
                  category: p.category ?? undefined,
                  imageUrl: p.image_url,
                  latitude: p.latitude,
                  longitude: p.longitude,
                });
              }
            }}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Ajouter à mon voyage
          </Button>
          <Button href="/mon-voyage" size="sm" variant="secondary">
            Voir mon voyage
          </Button>
        </div>
      ) : null}

      {(sources?.some((s) => s.url) || false) ? (
        <div>
          <p className="mb-2 text-sm font-semibold text-[var(--green-deep)]">
            {t('sources.title')} utilisées
          </p>
          <ul className="space-y-1 text-sm">
            {sources!
              .filter((s) => s.url)
              .map((s, i) => (
                <li key={`${s.url}-${i}`}>
                  <a
                    href={s.url!}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--green)] underline"
                  >
                    {s.title || s.url}
                  </a>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function HotelMiniCard({ hotel }: { hotel: ChatHotel | ChatPlace }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--mint-soft)]">
          <Hotel className="h-5 w-5 text-[var(--green)]" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-[var(--green-deep)]">{hotel.name}</p>
          <p className="mt-0.5 flex items-center gap-1 text-sm text-[var(--muted)]">
            <MapPin className="h-3.5 w-3.5" aria-hidden />
            {[hotel.city, hotel.region].filter(Boolean).join(', ') || 'Cameroun'}
          </p>
          {'price' in hotel && hotel.price ? (
            <Badge tone="gold">{hotel.price}</Badge>
          ) : 'estimated_cost_xaf' in hotel &&
            typeof hotel.estimated_cost_xaf === 'number' ? (
            <Badge tone="gold">{hotel.estimated_cost_xaf} FCFA</Badge>
          ) : (
            <Badge tone="muted">Indicatif / démo</Badge>
          )}
        </div>
      </div>
    </div>
  );
}

export function ItineraryCard({
  itinerary,
  fallbackText,
}: {
  itinerary?: ChatItinerary | null;
  fallbackText?: string | null;
}) {
  if (!itinerary?.days?.length && !fallbackText) return null;
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg font-semibold text-[var(--green-deep)]">
        {itinerary?.title || 'Votre voyage au Cameroun'}
      </h3>
      {itinerary?.destination ? (
        <p className="mt-1 flex items-center gap-1 text-sm text-[var(--muted)]">
          <MapPin className="h-3.5 w-3.5" aria-hidden />
          {itinerary.destination}
        </p>
      ) : null}
      {itinerary?.days?.length ? (
        <ul className="mt-4 space-y-3">
          {itinerary.days.map((d, i) => (
            <li
              key={`${d.day ?? i}-${d.title ?? i}`}
              className="rounded-xl border border-[var(--line)] bg-[var(--ivory)] px-4 py-3"
            >
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--gold)]">
                <Calendar className="h-3.5 w-3.5" aria-hidden />
                Jour {d.day ?? i + 1}
              </p>
              {d.title ? (
                <p className="mt-1 font-medium text-[var(--green-deep)]">{d.title}</p>
              ) : null}
              {d.summary ? (
                <p className="mt-1 text-sm text-[var(--muted)]">{d.summary}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : fallbackText ? (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{fallbackText}</p>
      ) : null}
    </div>
  );
}

export function BudgetCardFromApi({ budget }: { budget: ChatBudget }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg font-semibold text-[var(--green-deep)]">
        Budget estimé
      </h3>
      {typeof budget.total_xaf === 'number' ? (
        <p className="mt-2 text-2xl font-bold text-[var(--green-deep)]">
          {budget.total_xaf.toLocaleString('fr-FR')} {budget.currency || 'FCFA'}
        </p>
      ) : null}
      {budget.lines?.length ? (
        <ul className="mt-3 space-y-2 text-sm">
          {budget.lines.map((l) => (
            <li key={l.label} className="flex justify-between gap-4">
              <span>{l.label}</span>
              <span className="font-medium">
                {typeof l.amount_xaf === 'number'
                  ? `${l.amount_xaf.toLocaleString('fr-FR')} FCFA`
                  : 'Information non disponible'}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {budget.note ? (
        <p className="mt-3 text-xs text-[var(--muted)]">{budget.note}</p>
      ) : null}
    </div>
  );
}

export function BudgetCard({
  lines,
}: {
  lines: { label: string; amount: string | null }[];
}) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg font-semibold text-[var(--green-deep)]">
        Budget estimatif
      </h3>
      <ul className="mt-3 space-y-2 text-sm">
        {lines.map((l) => (
          <li key={l.label} className="flex justify-between gap-4">
            <span>{l.label}</span>
            <span className="font-medium">{l.amount ?? 'Information non disponible'}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 border-t border-[var(--line)] pt-3 text-sm text-[var(--muted)]">
        Seuls les montants fournis par le backend sont affichés.
      </p>
    </div>
  );
}

export function PlaceCarousel({ places }: { places: ChatPlace[] }) {
  return (
    <div className="flex gap-4 overflow-x-auto no-scrollbar pb-2">
      {places.map((p) => (
        <div key={p.id} className="w-72 shrink-0">
          <PlaceCard site={p} />
        </div>
      ))}
    </div>
  );
}

export function SourcesList({ sources }: { sources: ChatSource[] }) {
  const withUrl = sources.filter((s) => s.url);
  if (!withUrl.length) return null;
  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-[var(--green-deep)]">Sources utilisées</p>
      <ul className="space-y-1 text-sm">
        {withUrl.map((s, i) => (
          <li key={`${s.url}-${i}`}>
            <Link href={s.url!} className="text-[var(--green)] underline" target="_blank">
              {s.title || s.url}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
