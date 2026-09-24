'use client';

import { MapPin } from 'lucide-react';
import Link from 'next/link';

import { PlaceCard } from '@/components/places/PlaceCard';
import { TourismMap } from '@/components/maps/TourismMap';
import { Badge, Button } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { addPlaceToTrip } from '@/lib/trip-store';
import type {
  ActionUI,
  BookingUI,
  BudgetUI,
  ChatResponse,
  ChatResponseType,
  ChatSource,
  HotelUI,
  ItineraryUI,
  MapMarker,
  MapUI,
  PlaceUI,
  SourceUI,
  VisionUI,
} from '@/lib/types';

function mapToMarkers(map: MapUI | null | undefined): MapMarker[] {
  if (!map?.markers?.length) return [];
  return map.markers.map((m) => ({
    id: m.place_id,
    name: m.title,
    latitude: m.latitude,
    longitude: m.longitude,
  }));
}

export function ResponseRenderer({
  response,
  text,
  kind,
  sources,
  markers,
}: {
  response?: Partial<ChatResponse> | null;
  /** Legacy fallbacks when structured fields are absent. */
  text?: string;
  kind?: string;
  sources?: ChatSource[];
  markers?: MapMarker[];
}) {
  const { t } = useLocale();
  const body = response?.message || response?.text || text || '';
  const responseType = (response?.response_type || kind || 'SIMPLE_ANSWER') as ChatResponseType;
  const places = response?.places ?? [];
  const map = response?.map ?? null;
  const itinerary = response?.itinerary ?? null;
  const budget = response?.budget ?? null;
  const hotels = response?.hotels ?? [];
  const booking = response?.booking ?? null;
  const vision = response?.vision ?? null;
  const uiSources = response?.ui_sources ?? [];
  const actions = response?.actions ?? [];
  const legacySources = response?.sources ?? sources ?? [];
  const mapMarkers = mapToMarkers(map).length
    ? mapToMarkers(map)
    : markers ?? [];

  const showPlaces =
    places.length > 0 &&
    ['PLACE_LIST', 'PLACE_DETAILS', 'NATURE', 'CULTURE', 'FOOD', 'TOURISM_INFORMATION', 'PLACE_SEARCH'].includes(
      String(responseType),
    );

  const hasWeb =
    uiSources.some((s) => s.type === 'WEB' && s.url) ||
    legacySources.some((s) => Boolean(s.url));

  return (
    <div className="space-y-4">
      {body ? (
        <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--ink)]">
          {body}
        </div>
      ) : null}

      {hasWeb ? <Badge tone="yellow">{t('web.verified')}</Badge> : null}

      {vision ? <VisionBlock vision={vision} /> : null}

      {showPlaces || (places.length > 0 && !hotels.length) ? (
        <PlaceCarousel places={places} />
      ) : null}

      {hotels.length > 0 || responseType === 'HOTEL' ? (
        <HotelList hotels={hotels.length ? hotels : placesAsHotels(places)} />
      ) : null}

      {itinerary ? <ItineraryCard itinerary={itinerary} /> : null}

      {budget ? <BudgetCardStructured budget={budget} /> : null}

      {booking ? <BookingBlock booking={booking} /> : null}

      {mapMarkers.length > 0 ? (
        <TourismMap markers={mapMarkers} className="h-72" />
      ) : null}

      {actions.length > 0 ? <ActionsRow actions={actions} places={places} /> : null}

      <SourcesBlock uiSources={uiSources} legacy={legacySources} title={t('sources.title')} />
    </div>
  );
}

function placesAsHotels(places: PlaceUI[]): HotelUI[] {
  return places.map((p) => ({
    id: p.id,
    name: p.name,
    location: [p.city, p.region].filter(Boolean).join(', ') || null,
    image_url: p.image_url,
    description: p.description,
    price: p.estimated_cost_xaf ?? null,
    price_status: p.estimated_cost_xaf != null ? 'INDICATIVE' : 'UNKNOWN',
    amenities: [],
    booking_available: false,
    demo_booking: true,
    source_url: p.source_url,
  }));
}

function PlaceCarousel({ places }: { places: PlaceUI[] }) {
  if (!places.length) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {places.map((p) => (
        <PlaceCard
          key={p.id}
          site={{
            id: p.id,
            name: p.name,
            city: p.city,
            region: p.region,
            category: p.category,
            description: p.description ?? undefined,
            image_url: p.image_url,
            latitude: p.latitude,
            longitude: p.longitude,
          }}
          href={`/destinations/${encodeURIComponent(p.id)}`}
        />
      ))}
    </div>
  );
}

function HotelList({ hotels }: { hotels: HotelUI[] }) {
  if (!hotels.length) {
    return (
      <p className="text-sm text-[var(--muted)]">Aucun hôtel vérifié dans cette réponse.</p>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {hotels.map((h) => (
        <article
          key={h.id}
          className="rounded-2xl border border-[var(--line)] bg-white p-4 shadow-sm"
        >
          <h3 className="font-display text-lg text-[var(--green-deep)]">{h.name}</h3>
          {h.location ? (
            <p className="mt-1 flex items-start gap-1.5 text-sm text-[var(--muted)]">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>{h.location}</span>
            </p>
          ) : null}
          {h.description ? (
            <p className="mt-2 line-clamp-3 text-sm">{h.description}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="yellow">
              {h.price != null
                ? `${h.price.toLocaleString('fr-FR')} XAF (${h.price_status})`
                : 'Tarif inconnu'}
            </Badge>
            {h.demo_booking ? <Badge tone="muted">Démo</Badge> : null}
          </div>
          <div className="mt-3">
            <Button href={`/booking?hotel=${encodeURIComponent(h.id)}`} size="sm">
              Réserver (démo)
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}

function ItineraryCard({ itinerary }: { itinerary: ItineraryUI }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-xl text-[var(--green-deep)]">{itinerary.title}</h3>
      <div className="mt-4 space-y-5">
        {itinerary.days.map((day) => (
          <div key={day.day}>
            <p className="text-sm font-bold uppercase tracking-wide text-[var(--green)]">
              Jour {day.day}
            </p>
            <ul className="mt-2 space-y-2 border-l-2 border-[var(--yellow)] pl-4">
              {day.items.map((item, i) => (
                <li key={`${day.day}-${i}`} className="text-sm">
                  <span className="font-medium text-[var(--muted)]">
                    {item.time ?? '—'}
                  </span>{' '}
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="inline h-3.5 w-3.5 shrink-0" aria-hidden />
                    {item.title}
                  </span>
                  {item.duration_minutes != null
                    ? ` · ${item.duration_minutes} min`
                    : ''}
                  {item.place_id ? (
                    <>
                      {' '}
                      <Link
                        href={`/destinations/${encodeURIComponent(item.place_id)}`}
                        className="text-[var(--green)] underline"
                      >
                        voir
                      </Link>
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export function BudgetCardStructured({ budget }: { budget: BudgetUI }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg text-[var(--green-deep)]">Budget estimatif</h3>
      <ul className="mt-3 space-y-2 text-sm">
        {budget.items.map((l) => (
          <li key={l.label} className="flex justify-between gap-4">
            <span>{l.label}</span>
            <span className="font-medium">
              {l.amount != null
                ? `${l.amount.toLocaleString('fr-FR')} ${budget.currency}`
                : 'Non disponible'}
            </span>
          </li>
        ))}
      </ul>
      {budget.total_known != null ? (
        <p className="mt-4 border-t border-[var(--line)] pt-3 text-sm font-semibold">
          Total connu : {budget.total_known.toLocaleString('fr-FR')} {budget.currency}
        </p>
      ) : null}
      <p className="mt-2 text-xs text-[var(--muted)]">
        Seuls les montants fournis par le backend sont affichés.
      </p>
    </div>
  );
}

/** Legacy BudgetCard used by planner page. */
export function BudgetCard({
  lines,
}: {
  lines: { label: string; amount: string | null }[];
}) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg text-[var(--green-deep)]">Budget estimatif</h3>
      <ul className="mt-3 space-y-2 text-sm">
        {lines.map((l) => (
          <li key={l.label} className="flex justify-between gap-4">
            <span>{l.label}</span>
            <span className="font-medium">{l.amount ?? 'Non disponible'}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BookingBlock({ booking }: { booking: BookingUI }) {
  return (
    <div className="rounded-2xl border border-[var(--yellow)]/50 bg-[var(--yellow)]/15 p-4 text-sm">
      <Badge tone="yellow">Réservation de démonstration</Badge>
      <p className="mt-2">{booking.message ?? 'Booking demo only.'}</p>
    </div>
  );
}

function VisionBlock({ vision }: { vision: VisionUI }) {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-4">
      <h3 className="font-display text-lg text-[var(--green-deep)]">Vision</h3>
      {vision.description ? (
        <p className="mt-2 whitespace-pre-wrap text-sm">{vision.description}</p>
      ) : null}
      {vision.matched_place_id ? (
        <div className="mt-3">
          <Button href={`/destinations/${encodeURIComponent(vision.matched_place_id)}`} size="sm">
            Découvrir le lieu
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function ActionsRow({
  actions,
  places,
}: {
  actions: ActionUI[];
  places: PlaceUI[];
}) {
  const byPlace = new Map(places.map((p) => [p.id, p]));
  return (
    <div className="flex flex-wrap gap-2">
      {actions.slice(0, 8).map((a, i) => {
        if (a.type === 'VIEW_PLACE' && a.target_id) {
          return (
            <Button
              key={`${a.type}-${i}`}
              href={`/destinations/${encodeURIComponent(a.target_id)}`}
              size="sm"
              variant="secondary"
            >
              {a.label}
            </Button>
          );
        }
        if (a.type === 'ADD_TO_TRIP' && a.target_id) {
          const place = byPlace.get(a.target_id);
          return (
            <Button
              key={`${a.type}-${i}`}
              type="button"
              size="sm"
              onClick={() => {
                if (!place) return;
                addPlaceToTrip({
                  id: place.id,
                  name: place.name,
                  city: place.city ?? undefined,
                  region: place.region ?? undefined,
                  category: place.category ?? undefined,
                  imageUrl: place.image_url,
                  latitude: place.latitude,
                  longitude: place.longitude,
                });
              }}
            >
              {a.label}
            </Button>
          );
        }
        if (a.type === 'BOOK_HOTEL' && a.target_id) {
          return (
            <Button
              key={`${a.type}-${i}`}
              href={`/booking?hotel=${encodeURIComponent(a.target_id)}`}
              size="sm"
            >
              {a.label}
            </Button>
          );
        }
        if (a.type === 'VIEW_SOURCE' && a.target_id?.startsWith('http')) {
          return (
            <a
              key={`${a.type}-${i}`}
              href={a.target_id}
              target="_blank"
              rel="noreferrer"
              className="rounded-full bg-[var(--line)] px-3 py-1.5 text-xs font-semibold"
            >
              {a.label}
            </a>
          );
        }
        return null;
      })}
    </div>
  );
}

function SourcesBlock({
  uiSources,
  legacy,
  title,
}: {
  uiSources: SourceUI[];
  legacy: ChatSource[];
  title: string;
}) {
  const links =
    uiSources.filter((s) => s.url).length > 0
      ? uiSources.filter((s) => s.url)
      : legacy.filter((s) => s.url).map((s) => ({ title: s.title, url: s.url!, type: 'OTHER' }));
  if (!links.length) return null;
  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-[var(--green-deep)]">{title}</p>
      <ul className="space-y-1 text-sm">
        {links.map((s, i) => (
          <li key={`${s.url}-${i}`}>
            <a
              href={s.url!}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--green)] underline"
            >
              {s.title || s.url}
            </a>
            {'type' in s && s.type ? (
              <span className="ml-2 text-xs text-[var(--muted)]">{s.type}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
