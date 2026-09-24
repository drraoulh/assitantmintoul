/**
 * Smoke: structured ChatResponse → ResponseRenderer mapping fields.
 * Run: node scripts/smoke-response-renderer.js
 * Uses a real PLACE_LIST-shaped payload (no network).
 */
const placeList = {
  response_type: 'PLACE_LIST',
  message: 'Voici 3 lieux à Bafoussam.',
  text: 'Voici 3 lieux à Bafoussam.',
  places: [
    {
      id: 'chefferie-bafoussam',
      name: 'Chefferie de Bafoussam',
      city: 'Bafoussam',
      region: 'Ouest',
      category: 'Culture',
      description: 'Site traditionnel',
      image_url: null,
      latitude: null,
      longitude: null,
    },
    {
      id: 'route-artisans',
      name: 'Route des artisans (Bafoussam)',
      city: 'Bafoussam',
      region: 'Ouest',
      category: 'Culture',
      description: null,
      image_url: null,
      latitude: null,
      longitude: null,
    },
    {
      id: 'hauts-plateaux',
      name: 'Hauts Plateaux de l’Ouest',
      city: 'Bafoussam',
      region: 'Ouest',
      category: 'Nature',
      description: null,
      image_url: null,
      latitude: null,
      longitude: null,
    },
  ],
  map: null,
  itinerary: null,
  budget: null,
  hotels: [],
  sources: [{ title: 'KB', url: null }],
  actions: [{ type: 'OPEN_PLACE', label: 'Voir', place_id: 'chefferie-bafoussam' }],
};

const itinerary = {
  response_type: 'ITINERARY',
  message: 'Itinéraire 3 jours',
  places: [],
  itinerary: {
    title: '3 jours à Bafoussam',
    days: [{ day: 1, title: 'Jour 1', items: ['Chefferie'] }],
  },
  budget: null,
  hotels: [],
  sources: [],
  actions: [],
};

const budget = {
  response_type: 'BUDGET_TRIP',
  message: 'Budget indicatif',
  places: [],
  itinerary: null,
  budget: {
    currency: 'XAF',
    total_min: 50000,
    total_max: 120000,
    notes: 'Indicatif',
  },
  hotels: [],
  sources: [],
  actions: [],
};

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function wouldShowPlaces(response) {
  const responseType = response.response_type || 'SIMPLE_ANSWER';
  const places = response.places || [];
  return (
    places.length > 0 &&
    [
      'PLACE_LIST',
      'PLACE_DETAILS',
      'NATURE',
      'CULTURE',
      'FOOD',
      'TOURISM_INFORMATION',
      'PLACE_SEARCH',
    ].includes(String(responseType))
  );
}

assert(wouldShowPlaces(placeList), 'PLACE_LIST should show PlaceCarousel');
assert(placeList.places.length === 3, 'expected 3 places');
assert(Boolean(itinerary.itinerary), 'ITINERARY payload');
assert(Boolean(budget.budget), 'BUDGET_TRIP payload');
assert(!wouldShowPlaces(itinerary), 'ITINERARY alone should not force PlaceCarousel');

console.log('smoke-response-renderer: OK');
