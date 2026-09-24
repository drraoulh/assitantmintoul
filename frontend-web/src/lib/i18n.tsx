'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Locale = 'fr' | 'en';

type Dict = Record<string, string>;

const STRINGS: Record<Locale, Dict> = {
  fr: {
    'nav.explorer': 'Explorer',
    'nav.destinations': 'Destinations',
    'nav.planifier': 'Planifier',
    'nav.hotels': 'Hébergements',
    'nav.assistant': 'Assistant',
    'nav.trip': 'Mon voyage',
    'nav.vision': 'Vision',
    'hero.title': 'Découvrez le Cameroun',
    'hero.sub': 'avec une nouvelle façon de voyager.',
    'hero.body':
      'Explorez les destinations. Planifiez votre voyage. Découvrez les cultures. Laissez l’IA vous accompagner.',
    'hero.ctaExplore': 'Explorer le Cameroun',
    'hero.ctaPlan': 'Planifier mon voyage',
    'hero.ctaAssist': 'Parler à l’assistant',
    'home.assistantTitle': 'Votre assistant touristique',
    'home.assistantHint': '« Je suis à Bafoussam. Que puis-je visiter ? »',
    'home.placeholder': 'Écrivez votre question…',
    'status.checking': 'Connexion…',
    'status.waking': 'Connexion au serveur…',
    'status.online': 'Connecté',
    'status.offline': 'Connexion au serveur…',
    'error.generic': 'Une erreur est survenue. Veuillez réessayer.',
    'explorer.title': 'Explorer le Cameroun',
    'explorer.sub': 'Dix régions. Des lieux vérifiés dans la base SmartMboa.',
    'explorer.capital': 'Chef-lieu',
    'explorer.count': 'destinations',
    'explorer.cta': 'Explorer',
    'place.discover': 'Découvrir',
    'place.add': 'Ajouter au voyage',
    'place.added': 'Ajouté',
    'assistant.title': 'Assistant SmartMboa',
    'assistant.you': 'Vous',
    'assistant.bot': 'SmartMboa',
    'assistant.listening': 'Écoute…',
    'assistant.thinking': 'Analyse de votre demande…',
    'web.verified': 'Informations vérifiées en ligne',
    'sources.title': 'Sources',
    'map.loading': 'Chargement de la carte…',
    'map.empty': 'Aucune coordonnée vérifiée pour afficher la carte.',
    'planner.title': 'Planifier mon voyage',
    'planner.cta': 'Créer mon itinéraire',
    'hotels.title': 'Hébergements',
    'hotels.indicative': 'Tarif indicatif',
    'hotels.demo': 'Réservation de démonstration',
    'booking.title': 'Réservation',
    'booking.confirm': 'Confirmer',
    'booking.done': 'Réservation confirmée',
    'booking.demoNote': 'Réservation de démonstration — aucun paiement réel.',
    'trip.title': 'Mon voyage',
    'vision.title': 'Identifier un lieu',
    'vision.cta': 'Analyser la photo',
    'vision.fail': 'Nous n’avons pas pu identifier précisément ce lieu.',
    'loading.places': 'Recherche des destinations…',
    'empty.places': 'Aucun lieu trouvé pour cette sélection.',
  },
  en: {
    'nav.explorer': 'Explore',
    'nav.destinations': 'Destinations',
    'nav.planifier': 'Plan',
    'nav.hotels': 'Stays',
    'nav.assistant': 'Assistant',
    'nav.trip': 'My trip',
    'nav.vision': 'Vision',
    'hero.title': 'Discover Cameroon',
    'hero.sub': 'with a new way to travel.',
    'hero.body':
      'Explore destinations. Plan your trip. Discover cultures. Let AI guide you.',
    'hero.ctaExplore': 'Explore Cameroon',
    'hero.ctaPlan': 'Plan my trip',
    'hero.ctaAssist': 'Talk to the assistant',
    'home.assistantTitle': 'Your travel assistant',
    'home.assistantHint': '“I am in Bafoussam. What can I visit?”',
    'home.placeholder': 'Write your question…',
    'status.checking': 'Connecting…',
    'status.waking': 'Connecting to server…',
    'status.online': 'Online',
    'status.offline': 'Connecting to server…',
    'error.generic': 'Something went wrong. Please try again.',
    'explorer.title': 'Explore Cameroon',
    'explorer.sub': 'Ten regions. Places verified in the SmartMboa knowledge base.',
    'explorer.capital': 'Capital',
    'explorer.count': 'destinations',
    'explorer.cta': 'Explore',
    'place.discover': 'Discover',
    'place.add': 'Add to trip',
    'place.added': 'Added',
    'assistant.title': 'SmartMboa Assistant',
    'assistant.you': 'You',
    'assistant.bot': 'SmartMboa',
    'assistant.listening': 'Listening…',
    'assistant.thinking': 'Analyzing your request…',
    'web.verified': 'Information verified online',
    'sources.title': 'Sources',
    'map.loading': 'Loading map…',
    'map.empty': 'No verified coordinates to show on the map.',
    'planner.title': 'Plan my trip',
    'planner.cta': 'Create my itinerary',
    'hotels.title': 'Stays',
    'hotels.indicative': 'Indicative rate',
    'hotels.demo': 'Demo booking',
    'booking.title': 'Booking',
    'booking.confirm': 'Confirm',
    'booking.done': 'Booking confirmed',
    'booking.demoNote': 'Demo booking — no real payment.',
    'trip.title': 'My trip',
    'vision.title': 'Identify a place',
    'vision.cta': 'Analyze photo',
    'vision.fail': 'We could not precisely identify this place.',
    'loading.places': 'Searching destinations…',
    'empty.places': 'No places found for this selection.',
  },
};

interface LocaleCtx {
  locale: Locale;
  t: (key: string) => string;
  toggleLocale: () => void;
  setLocale: (l: Locale) => void;
}

const Ctx = createContext<LocaleCtx | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('fr');

  useEffect(() => {
    const saved = localStorage.getItem('smartmboa.locale');
    if (saved === 'fr' || saved === 'en') setLocaleState(saved);
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem('smartmboa.locale', l);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'fr' ? 'en' : 'fr');
  }, [locale, setLocale]);

  const t = useCallback(
    (key: string) => STRINGS[locale][key] ?? STRINGS.fr[key] ?? key,
    [locale],
  );

  const value = useMemo(
    () => ({ locale, t, toggleLocale, setLocale }),
    [locale, t, toggleLocale, setLocale],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useLocale outside provider');
  return ctx;
}
