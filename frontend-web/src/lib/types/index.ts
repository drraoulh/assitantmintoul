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

export interface ChatResponse {
  conversation_id: string;
  role: 'assistant';
  message: string;
  provider: string;
  sources?: ChatSource[];
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

/** Frontend-derived response kinds from chat text + sources (backend stays unchanged). */
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
