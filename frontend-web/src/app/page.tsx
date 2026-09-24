'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  Backpack,
  Camera,
  Compass,
  Hotel,
  MapPin,
  Mic,
  Sparkles,
  Utensils,
} from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';

import { FadeIn, SlideUp, StaggerContainer, StaggerItem } from '@/components/motion';
import { PlaceCard } from '@/components/places/PlaceCard';
import { Button, Input, Skeleton } from '@/components/ui';
import { ImmersiveWelcome } from '@/components/welcome/ImmersiveWelcome';
import { listTouristSites } from '@/lib/api/client';
import { APP_NAME } from '@/lib/config';
import { useLocale } from '@/lib/i18n';
import { REGIONS } from '@/lib/regions';
import { isHotelCategory } from '@/lib/utils/response';
import type { TouristSite } from '@/lib/types';

const CameroonSilhouette = dynamic(
  () =>
    import('@/components/maps/CameroonSilhouette').then((m) => m.CameroonSilhouette),
  { ssr: false, loading: () => <Skeleton className="mx-auto h-48 w-40" /> },
);

const QUICK = [
  {
    icon: MapPin,
    label: 'Lieux près de moi',
    href: '/assistant?q=Quels%20lieux%20touristiques%20v%C3%A9rifi%C3%A9s%20puis-je%20visiter%20au%20Cameroun%20%3F',
  },
  {
    icon: Compass,
    label: 'Planifier un voyage',
    href: '/planifier',
  },
  {
    icon: Backpack,
    label: 'Découvrir la culture',
    href: '/assistant?q=Parle-moi%20de%20la%20culture%20et%20des%20chefferies%20au%20Cameroun',
  },
  {
    icon: Sparkles,
    label: 'Explorer la nature',
    href: '/assistant?q=Quels%20parcs%20et%20sites%20nature%20v%C3%A9rifi%C3%A9s%20recommandez-vous%20au%20Cameroun%20%3F',
  },
  {
    icon: Utensils,
    label: 'Découvrir la gastronomie',
    href: '/assistant?q=Quels%20plats%20et%20exp%C3%A9riences%20culinaires%20camerounaises%20puis-je%20d%C3%A9couvrir%20%3F',
  },
] as const;

export default function HomePage() {
  const { t } = useLocale();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [q, setQ] = useState('');
  const [places, setPlaces] = useState<TouristSite[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loadingPlaces, setLoadingPlaces] = useState(true);
  const onIntroComplete = useCallback(() => setReady(true), []);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await listTouristSites();
        if (cancelled) return;
        const sites = res.items.filter((s) => !isHotelCategory(s.category));
        setPlaces(sites.slice(0, 6));
        const next: Record<string, number> = {};
        for (const r of REGIONS) {
          next[r.id] = res.items.filter(
            (s) => s.region.trim().toLowerCase() === r.apiRegion.trim().toLowerCase(),
          ).length;
        }
        setCounts(next);
      } catch {
        /* empty — home still usable */
      } finally {
        if (!cancelled) setLoadingPlaces(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready]);

  function onAsk(e: FormEvent) {
    e.preventDefault();
    const message = q.trim();
    if (message) {
      router.push(`/assistant?q=${encodeURIComponent(message)}`);
    } else {
      router.push('/assistant');
    }
  }

  return (
    <>
      {!ready ? <ImmersiveWelcome onComplete={onIntroComplete} /> : null}

      <div
        className={`transition-opacity duration-700 ${ready ? 'opacity-100' : 'opacity-0'}`}
      >
        {/* Conversational hero */}
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 opacity-80"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 90% -10%, rgba(214,168,79,0.18), transparent 55%), radial-gradient(ellipse 60% 40% at 0% 100%, rgba(20,92,67,0.12), transparent 50%)',
            }}
          />
          <div className="relative mx-auto max-w-3xl px-4 pb-10 pt-12 md:px-6 md:pt-16">
            <SlideUp>
              <p className="text-sm font-medium text-[var(--gold)]">Bonjour</p>
              <h1 className="mt-2 font-display text-3xl font-bold leading-tight text-[var(--green-deep)] md:text-4xl">
                Que souhaitez-vous découvrir au Cameroun ?
              </h1>
              <p className="mt-3 text-[var(--muted)]">
                {APP_NAME} — votre guide intelligent pour explorer, planifier et voyager.
              </p>
            </SlideUp>

            <FadeIn delay={0.1} className="mt-8">
              <form
                onSubmit={onAsk}
                className="flex items-center gap-2 rounded-full border border-[var(--line)] bg-white p-2 shadow-[var(--shadow-soft)]"
              >
                <label className="sr-only" htmlFor="home-ask">
                  Demandez à SmartMboa
                </label>
                <Input
                  id="home-ask"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Demandez-moi quelque chose…"
                  className="border-0 shadow-none focus:ring-0"
                />
                <button
                  type="button"
                  aria-label="Parler à l'assistant"
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--mint-soft)] text-[var(--green-deep)] hover:bg-[var(--line)]"
                  onClick={() => router.push('/assistant?voice=1')}
                >
                  <Mic className="h-5 w-5" />
                </button>
                <button
                  type="submit"
                  aria-label="Envoyer"
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--green-deep)] text-white hover:bg-[var(--green)]"
                >
                  <ArrowRight className="h-5 w-5" />
                </button>
              </form>
            </FadeIn>

            <div className="mt-5 flex gap-2 overflow-x-auto no-scrollbar pb-1">
              {QUICK.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  className="inline-flex shrink-0 items-center gap-2 rounded-full border border-[var(--line)] bg-white px-3.5 py-2 text-sm text-[var(--ink)] transition hover:border-[var(--gold)] hover:bg-[var(--mint-soft)]"
                >
                  <item.icon className="h-4 w-4 text-[var(--green)]" aria-hidden />
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Explore Cameroon */}
        <section className="mx-auto max-w-6xl px-4 py-14 md:px-6">
          <div className="grid items-center gap-10 lg:grid-cols-[0.9fr_1.1fr]">
            <SlideUp className="text-center lg:text-left">
              <div className="mx-auto lg:mx-0">
                <CameroonSilhouette size="md" glow />
              </div>
            </SlideUp>
            <div>
              <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
                Explorez le Cameroun
              </h2>
              <p className="mt-2 text-[var(--muted)]">
                10 régions. Des dizaines d&apos;expériences vérifiées.
              </p>
              <StaggerContainer className="mt-6 grid gap-3 sm:grid-cols-2">
                {REGIONS.map((r) => {
                  const count = counts[r.id];
                  return (
                    <StaggerItem key={r.id}>
                      <Link
                        href={`/destinations?region=${encodeURIComponent(r.apiRegion)}`}
                        className="group block rounded-2xl border border-[var(--line)] bg-white px-4 py-3 transition hover:-translate-y-0.5 hover:border-[var(--gold)]/50 hover:shadow-[var(--shadow-soft)]"
                      >
                        <p className="font-semibold text-[var(--green-deep)]">{r.nameFr}</p>
                        <p className="text-sm text-[var(--muted)]">
                          {r.capitalFr}
                          {typeof count === 'number' && count > 0
                            ? ` · ${count} lieux`
                            : ''}
                        </p>
                      </Link>
                    </StaggerItem>
                  );
                })}
              </StaggerContainer>
              <div className="mt-6">
                <Button href="/explorer" variant="outline">
                  Voir l&apos;explorateur
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Popular destinations */}
        <section className="bg-[var(--mint-soft)]/60 py-14">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
              Destinations vérifiées
            </h2>
            <p className="mt-2 text-[var(--muted)]">
              Issus de la base SmartMboa — aucune invention côté interface.
            </p>
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {loadingPlaces
                ? Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-72 w-full" />
                  ))
                : places.map((site) => <PlaceCard key={site.id} site={site} />)}
            </div>
            {!loadingPlaces && places.length === 0 ? (
              <p className="mt-6 text-sm text-[var(--muted)]">
                Les destinations se chargeront dès que l&apos;API sera disponible.
              </p>
            ) : null}
            <div className="mt-8">
              <Button href="/destinations" variant="secondary">
                Toutes les destinations
              </Button>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section className="mx-auto max-w-6xl px-4 py-14 md:px-6">
          <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
            Ce que {APP_NAME} peut faire
          </h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Sparkles,
                title: 'Assistant IA',
                body: 'Posez une question en texte ou en voix — réponses ancrées dans la connaissance vérifiée.',
                href: '/assistant',
              },
              {
                icon: Camera,
                title: 'Vision',
                body: 'Photographiez un lieu et laissez Gemini Vision + SmartMboa vous guider.',
                href: '/vision',
              },
              {
                icon: Hotel,
                title: 'Planifier & séjourner',
                body: 'Itinéraires, budget et hébergements issus des données disponibles.',
                href: '/planifier',
              },
            ].map((card) => (
              <Link
                key={card.href}
                href={card.href}
                className="group border-t border-[var(--line)] pt-5 transition hover:border-[var(--gold)]"
              >
                <card.icon className="h-6 w-6 text-[var(--green)]" aria-hidden />
                <h3 className="mt-3 font-display text-xl font-semibold text-[var(--green-deep)]">
                  {card.title}
                </h3>
                <p className="mt-2 text-sm text-[var(--muted)]">{card.body}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* Final CTA */}
        <section className="bg-[var(--green-deep)] py-16 text-white">
          <div className="mx-auto max-w-3xl px-4 text-center md:px-6">
            <h2 className="font-display text-3xl font-bold md:text-4xl">
              Votre prochaine aventure commence ici.
            </h2>
            <p className="mt-3 text-white/80">
              Découvrez le Cameroun avec {APP_NAME}.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Button href="/assistant" variant="gold" size="lg">
                Commencer l&apos;exploration
                <ArrowRight className="h-5 w-5" aria-hidden />
              </Button>
              <Button href="/explorer" variant="ghost" size="lg">
                {t('hero.ctaExplore')}
              </Button>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
