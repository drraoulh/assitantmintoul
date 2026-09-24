export type ChatRole = 'user' | 'assistant';
export type ChatMode = 'text' | 'voice';
export type ChatLocale = 'fr' | 'en';
export type BackendStatus = 'checking' | 'waking' | 'online' | 'offline';

export type ChatResponseType =
  | 'SIMPLE_ANSWER'
  | 'TOURISM_INFORMATION'
  | 'PLACE_LIST'
  | 'PLACE_DETAILS'
  | 'ITINERARY'
  | 'BUDGET_TRIP'
  | 'NATURE'
  | 'CULTURE'
  | 'FOOD'
  | 'HOTEL'
  | 'BOOKING'
  | 'VISION'
  | 'CLARIFICATION'
  | 'INSUFFICIENT_INFORMATION'
  | string;

export interface ChatSource {
  title: string;
  city?: string | null;
  region?: string | null;
  category?: string | null;
  organization?: string | null;
  url?: string | null;
  image_url?: string | null;
}

export interface PlaceUI {
  id: string;
  name: string;
  description?: string | null;
  category?: string | null;
  city?: string | null;
  region?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  image_url?: string | null;
  source_url?: string | null;
  estimated_cost_xaf?: number | null;
}

export interface MapMarkerUI {
  place_id: string;
  latitude: number;
  longitude: number;
  title: string;
}

export interface MapUI {
  enabled: boolean;
  center: { latitude: number; longitude: number };
  markers: MapMarkerUI[];
}

export interface ItineraryItemUI {
  time?: string | null;
  place_id?: string | null;
  title: string;
  duration_minutes?: number | null;
}

export interface ItineraryUI {
  title: string;
  days: { day: number; items: ItineraryItemUI[] }[];
}

export interface BudgetUI {
  currency: string;
  items: { label: string; amount: number | null; status: string }[];
  total_known?: number | null;
}

export interface HotelUI {
  id: string;
  name: string;
  location?: string | null;
  image_url?: string | null;
  description?: string | null;
  price?: number | null;
  price_status: string;
  amenities: string[];
  booking_available: boolean;
  demo_booking: boolean;
  source_url?: string | null;
}

export interface BookingUI {
  available: boolean;
  demo: boolean;
  message?: string | null;
}

export interface VisionUI {
  description?: string | null;
  matched_place_id?: string | null;
  confidence?: number | null;
}

export interface SourceUI {
  title: string;
  url?: string | null;
  type: 'WEB' | 'KB' | 'OTHER' | string;
}

export interface ActionUI {
  type: string;
  label: string;
  target_id?: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  mode?: ChatMode;
  locale?: ChatLocale;
}

export interface ChatResponse {
  conversation_id: string;
  role: 'assistant';
  message: string;
  text?: string | null;
  provider: string;
  sources?: ChatSource[];
  response_type?: ChatResponseType | null;
  places?: PlaceUI[];
  map?: MapUI | null;
  itinerary?: ItineraryUI | null;
  budget?: BudgetUI | null;
  hotels?: HotelUI[];
  booking?: BookingUI | null;
  vision?: VisionUI | null;
  ui_sources?: SourceUI[];
  actions?: ActionUI[];
  structured_build_ms?: number | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  updated_at?: string | null;
}

export interface ConversationListResponse {
  items: ConversationSummary[];
  count: number;
  persistent: boolean;
}

export interface ConversationTurn {
  role: ChatRole;
  content: string;
  created_at?: string | null;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  messages: ConversationTurn[];
  count: number;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface SourceRecord {
  title: string;
  organization?: string | null;
  url?: string | null;
  publication_date?: string | null;
  verification_status?: string;
}

export interface TouristSite {
  id: string;
  name: string;
  slug: string;
  region: string;
  city: string;
  category: string;
  description: string;
  history?: string | null;
  culture?: string | null;
  activities: string[];
  latitude?: number | null;
  longitude?: number | null;
  opening_hours?: string | null;
  price?: string | null;
  languages: string[];
  images: string[];
  sources: SourceRecord[];
}

export interface TouristSiteListResponse {
  items: TouristSite[];
  count: number;
}

export interface VisionIdentifyResponse {
  description: string;
  provider: string;
}

/** @deprecated Prefer ChatResponseType from the API. */
export type ResponseKind =
  | 'PLACE_SEARCH'
  | 'PLACE_DETAILS'
  | 'ITINERARY'
  | 'HOTEL'
  | 'BOOKING'
  | 'VISION'
  | 'SIMPLE_ANSWER';

export interface MapMarker {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  category?: string;
}

export interface TripPlace {
  id: string;
  name: string;
  city?: string;
  region?: string;
  category?: string;
  imageUrl?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface DemoBooking {
  reference: string;
  hotelName: string;
  hotelId: string;
  checkIn: string;
  checkOut: string;
  guests: number;
  guestName: string;
  guestEmail: string;
  createdAt: string;
  demo: true;
}

export interface TripState {
  destination?: string;
  dates?: string;
  travelers?: number;
  budgetFcfa?: number;
  interests?: string[];
  style?: string;
  places: TripPlace[];
  itineraryText?: string;
  hotel?: TripPlace | null;
  bookings: DemoBooking[];
}
