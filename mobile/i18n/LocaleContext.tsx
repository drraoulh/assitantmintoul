import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NativeModules, Platform } from 'react-native';

import { STRINGS } from './strings';
import type { AppLocale, TranslationKey } from './types';

const STORAGE_KEY = 'smartmboa.locale';

type LocaleContextValue = {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  toggleLocale: () => void;
  t: (key: TranslationKey) => string;
  speechLanguage: string;
  dateLocale: string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function deviceLocale(): AppLocale {
  try {
    if (Platform.OS === 'web' && typeof navigator !== 'undefined') {
      const lang = (navigator.language || 'fr').toLowerCase();
      return lang.startsWith('en') ? 'en' : 'fr';
    }
    const settings = NativeModules.SettingsManager?.settings;
    const raw =
      Platform.OS === 'ios'
        ? settings?.AppleLocale || settings?.AppleLanguages?.[0]
        : NativeModules.I18nManager?.localeIdentifier;
    const lang = String(raw || 'fr').toLowerCase();
    return lang.startsWith('en') ? 'en' : 'fr';
  } catch {
    return 'fr';
  }
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>('fr');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await AsyncStorage.getItem(STORAGE_KEY);
        if (!cancelled) {
          if (stored === 'fr' || stored === 'en') {
            setLocaleState(stored);
          } else {
            setLocaleState(deviceLocale());
          }
        }
      } catch {
        if (!cancelled) {
          setLocaleState(deviceLocale());
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    void AsyncStorage.setItem(STORAGE_KEY, next);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'fr' ? 'en' : 'fr');
  }, [locale, setLocale]);

  const t = useCallback(
    (key: TranslationKey) => STRINGS[locale][key] ?? STRINGS.fr[key] ?? key,
    [locale],
  );

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      toggleLocale,
      t,
      speechLanguage: locale === 'en' ? 'en-US' : 'fr-FR',
      dateLocale: locale === 'en' ? 'en-GB' : 'fr-FR',
    }),
    [locale, setLocale, toggleLocale, t],
  );

  // Avoid flashing wrong language before storage loads.
  if (!ready) {
    return null;
  }

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error('useLocale must be used within LocaleProvider');
  }
  return ctx;
}
