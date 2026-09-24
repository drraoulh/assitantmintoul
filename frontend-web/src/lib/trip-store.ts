import type { DemoBooking, TripPlace, TripState } from './types';

const KEY = 'smartmboa.trip.v1';

const empty: TripState = {
  places: [],
  hotel: null,
  bookings: [],
};

export function loadTrip(): TripState {
  if (typeof window === 'undefined') return empty;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as TripState;
    return {
      ...empty,
      ...parsed,
      places: parsed.places ?? [],
      bookings: parsed.bookings ?? [],
    };
  } catch {
    return empty;
  }
}

export function saveTrip(trip: TripState): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(KEY, JSON.stringify(trip));
}

export function addPlaceToTrip(place: TripPlace): TripState {
  const trip = loadTrip();
  if (trip.places.some((p) => p.id === place.id)) return trip;
  const next = { ...trip, places: [...trip.places, place] };
  saveTrip(next);
  return next;
}

export function setTripMeta(
  meta: Partial<
    Pick<
      TripState,
      'destination' | 'dates' | 'travelers' | 'budgetFcfa' | 'interests' | 'style' | 'itineraryText'
    >
  >,
): TripState {
  const trip = { ...loadTrip(), ...meta };
  saveTrip(trip);
  return trip;
}

export function setTripHotel(hotel: TripPlace | null): TripState {
  const trip = { ...loadTrip(), hotel };
  saveTrip(trip);
  return trip;
}

export function addBooking(booking: DemoBooking): TripState {
  const trip = loadTrip();
  const next = { ...trip, bookings: [...trip.bookings, booking], hotel: trip.hotel };
  saveTrip(next);
  return next;
}

export function makeBookingRef(): string {
  const n = Math.floor(100000 + Math.random() * 900000);
  return `SMB-${n}`;
}
