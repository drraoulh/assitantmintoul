export type ChatRole = 'user' | 'assistant';
export type ChatMode = 'text' | 'voice';
export type ChatLocale = 'fr' | 'en';
export type BackendStatus = 'checking' | 'waking' | 'online' | 'offline';

/** Mirrors backend ChatResponseType (Phase 3.1). */
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
  | 'TRAVEL_ROUTE'
  | 'IMAGES'
  | string;

/** @deprecated Prefer ChatResponseType — kept for older call sites. */
export type ResponseKind = ChatResponseType;

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

/** PlaceUI */
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

/** Alias used across the app */
export type ChatPlace = PlaceUI;

export interface MapMarkerUI {
  place_id: string;
  latitude: number;
  longitude: number;
  title: string;
}

export interface MapCenterUI {
  latitude: number;
  longitude: number;
}

export interface MapUI {
  enabled?: boolean;
  center: MapCenterUI;
  markers?: MapMarkerUI[];
}

export interface ItineraryItemUI {
  time?: string | null;
  place_id?: string | null;
  title: string;
  duration_minutes?: number | null;
}

export interface ItineraryDayUI {
  day: number;
  items?: ItineraryItemUI[];
}

export interface ItineraryUI {
  title: string;
  days?: ItineraryDayUI[];
}

export type ChatItinerary = ItineraryUI;
export type ChatItineraryDay = ItineraryDayUI;

export interface BudgetItemUI {
  label: string;
  amount?: number | null;
  status?: 'KNOWN' | 'UNKNOWN' | 'INDICATIVE';
}

export interface BudgetUI {
  currency?: string;
  items?: BudgetItemUI[];
  total_known?: number | null;
}

export type ChatBudget = BudgetUI;

export interface HotelUI {
  id: string;
  name: string;
  location?: string | null;
  image_url?: string | null;
  description?: string | null;
  price?: number | null;
  price_status?: 'KNOWN' | 'INDICATIVE' | 'UNKNOWN';
  amenities?: string[];
  booking_available?: boolean;
  demo_booking?: boolean;
  source_url?: string | null;
}

export type ChatHotel = HotelUI;

export interface BookingUI {
  available?: boolean;
  demo?: boolean;
  message?: string | null;
}

export interface VisionUI {
  description?: string | null;
  matched_place_id?: string | null;
  confidence?: number | null;
}

export type ChatVisionPayload = VisionUI;

export interface SourceUI {
  title: string;
  url?: string | null;
  type?: 'WEB' | 'KB' | 'OTHER';
}

export type ActionType =
  | 'VIEW_PLACE'
  | 'ADD_TO_TRIP'
  | 'VIEW_MAP'
  | 'PLAN_TRIP'
  | 'BOOK_HOTEL'
  | 'ASK_AI'
  | 'VIEW_SOURCE';

export interface ActionUI {
  type: ActionType | string;
  label: string;
  target_id?: string | null;
}

/** Web image result — URLs come from the image search provider. */
export interface ImageUI {
  image_url: string;
  thumbnail_url?: string | null;
  page_url: string;
  title?: string;
  source_domain?: string;
}

/** Intent the backend routed the message to (web-first chat). */
export interface ChatRoutingUI {
  chat_intent: string;
  intent: string;
  location?: string | null;
  origin?: string | null;
  destination?: string | null;
  dish?: string | null;
  duration_days?: number | null;
  wants_images?: boolean;
  is_route?: boolean;
  web_reason?: string | null;
}

/**
 * Structured UI block attached to HTTP ChatResponse and voice `turn_done.ui`.
 */
export interface StructuredChatUI {
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
  images?: ImageUI[];
  routing?: ChatRoutingUI | null;
  structured_build_ms?: number | null;
}

/**
 * Full HTTP ChatResponse (Expo-compatible + Phase 3.1 structured fields).
 */
export interface ChatResponse extends StructuredChatUI {
  conversation_id: string;
  role?: 'assistant';
  message: string;
  provider: string;
  sources?: ChatSource[];
  text?: string | null;
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
