export type ChatRole = 'user' | 'assistant';
export type ChatMode = 'text' | 'voice';
export type ChatLocale = 'fr' | 'en';
export type BackendStatus = 'checking' | 'waking' | 'online' | 'offline';

export interface ChatSource {
  title: string;
  city?: string | null;
  region?: string | null;
  category?: string | null;
  organization?: string | null;
  url?: string | null;
  image_url?: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  mode?: ChatMode;
  locale?: ChatLocale;
}

/** Place payload returned by structured ChatResponse (when present). */
export interface ChatPlace {
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

export interface ChatMapMarker {
  id?: string;
  name?: string;
  latitude: number;
  longitude: number;
  category?: string | null;
}

export interface ChatMapPayload {
  markers?: ChatMapMarker[] | null;
  center?: { latitude: number; longitude: number } | null;
}

export interface ChatItineraryDay {
  day?: number;
  title?: string | null;
  summary?: string | null;
  places?: ChatPlace[] | null;
  activities?: string[] | null;
}

export interface ChatItinerary {
  title?: string | null;
  destination?: string | null;
  days?: ChatItineraryDay[] | null;
  summary?: string | null;
}

export interface ChatBudget {
  total_xaf?: number | null;
  currency?: string | null;
  lines?: { label: string; amount_xaf?: number | null }[] | null;
  note?: string | null;
}

export interface ChatHotel {
  id?: string;
  name: string;
  city?: string | null;
  region?: string | null;
  category?: string | null;
  price?: string | null;
  image_url?: string | null;
  description?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface ChatVisionPayload {
  description?: string | null;
  matched_place_id?: string | null;
  confidence?: number | null;
}

/**
 * Chat API response. Core fields always present; structured fields
 * (response_type, places, …) are consumed when the orchestrator returns them.
 */
export interface ChatResponse {
  conversation_id: string;
  role: 'assistant';
  message: string;
  provider: string;
  sources?: ChatSource[];
  text?: string;
  response_type?: string | null;
  places?: ChatPlace[] | null;
  map?: ChatMapPayload | null;
  itinerary?: ChatItinerary | null;
  budget?: ChatBudget | null;
  hotels?: ChatHotel[] | null;
  booking?: unknown;
  vision?: ChatVisionPayload | null;
  ui_sources?: ChatSource[] | null;
  actions?: { label: string; href?: string; type?: string }[] | null;
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

/** Frontend response kinds — prefer backend response_type when available. */
export type ResponseKind =
  | 'PLACE_LIST'
  | 'PLACE_SEARCH'
  | 'PLACE_DETAILS'
  | 'ITINERARY'
  | 'BUDGET_TRIP'
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
