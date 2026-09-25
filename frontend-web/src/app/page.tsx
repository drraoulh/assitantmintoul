'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  Camera,
  Compass,
  Hotel,
  MapPin,
  Mic,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';

import { PlaceCard } from '@/components/places/PlaceCard';
import { RegionCoverGrid } from '@/components/places/RegionCoverCard';
import { Button, Input, Skeleton } from '@/components/ui';
import { SmartMboaIntro } from '@/components/intro/SmartMboaIntro';
import { listTouristSites } from '@/lib/api/client';
import { APP_NAME } from '@/lib/config';
import { useLocale } from '@/lib/i18n';
import { MUST_SEE_IDS, resolvePlaceImage } from '@/lib/place-images';
import { REGIONS } from '@/lib/regions';
import { isHotelCategory } from '@/lib/utils/response';
import type { TouristSite } from '@/lib/types';

export default function HomePage() {
  const { t } = useLocale();
  const router = useRouter();
  const [ready, setReady] = useState(true);
  const [q, setQ] = useState('');
  const [allPlaces, setAllPlaces] = useState<TouristSite[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loadingPlaces, setLoadingPlaces] = useState(true);
  const onIntroComplete = useCallback(() => setReady(true), []);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('reset_intro') === '1') {
      setReady(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await listTouristSites();
        if (cancelled) return;
        const sites = res.items.filter((s) => !isHotelCategory(s.category));
        setAllPlaces(sites);
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

  const mustSee = useMemo(() => {
    const byId = new Map(allPlaces.map((p) => [p.id, p]));
    const ordered: TouristSite[] = [];
    for (const id of MUST_SEE_IDS) {
      const hit = byId.get(id);
      if (hit) ordered.push(hit);
    }
    if (ordered.length >= 4) return ordered;
    // Fallback: prefer places that have a resolvable image
    const extras = allPlaces.filter(
      (p) => !ordered.some((o) => o.id === p.id) && resolvePlaceImage(p),
    );
    return [...ordered, ...extras].slice(0, 10);
  }, [allPlaces]);

  const experiences = useMemo(() => {
    const nature = allPlaces.filter((p) => /nature|park|beach/i.test(p.category)).slice(0, 3);
    const culture = allPlaces
      .filter((p) => /culture|heritage|museum/i.test(p.category))
      .slice(0, 3);
    return [...nature, ...culture].slice(0, 6);
  }, [allPlaces]);

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
      {!ready ? <SmartMboaIntro onComplete={onIntroComplete} /> : null}

      <div className={ready ? '' : 'hidden'}>
        <section className="relative overflow-hidden bg-gradient-to-br from-white via-[#007A5E]/5 to-[#FCD116]/35">
          <div className="mx-auto flex max-w-6xl flex-col-reverse items-center gap-10 px-4 py-14 sm:px-8 md:flex-row md:gap-6 md:py-20 lg:px-12">
            <div className="w-full md:w-1/2">
              <h1 className="text-center text-3xl font-bold tracking-tight text-black sm:text-4xl md:text-left lg:text-[52px] lg:leading-[56px]">
                Explorez le{' '}
                <span className="text-[#CE1126]">Cameroun</span>
                <br />
                avec passion et confiance
              </h1>
              <p className="mx-auto mt-6 max-w-xl text-center text-lg font-semibold text-[#007A5E] sm:text-xl md:mx-0 md:text-left lg:text-2xl">
                Sites, culture, nature et itinéraires — un seul guide intelligent.
              </p>
              <div className="mt-8 flex flex-col gap-4 sm:flex-row md:mt-10">
                <Link
                  href="/explorer"
                  className="rounded-full bg-[#007A5E] px-8 py-3 text-center text-base font-bold text-white shadow-md hover:bg-[#00614b]"
                >
                  Découvrir nos sites
                </Link>
                <Link
                  href="/assistant"
                  className="rounded-full bg-white px-8 py-3 text-center text-base font-bold text-[#CE1126] shadow-md ring-1 ring-[#CE1126]/20 hover:bg-[#fff6f6]"
                >
                  Parler à l&apos;assistant
                </Link>
              </div>
              <form onSubmit={onAsk} className="mt-8 flex items-center gap-2 rounded-full border border-gray-200 bg-white p-2 shadow-lg">
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
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#FCD116] text-[#1a1a1a] hover:brightness-95"
                  onClick={() => router.push('/assistant?voice=1')}
                >
                  <Mic className="h-5 w-5" />
                </button>
                <button
                  type="submit"
                  aria-label="Envoyer"
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#007A5E] text-white hover:bg-[#00614b]"
                >
                  <ArrowRight className="h-5 w-5" />
                </button>
              </form>
            </div>
            <div className="relative flex w-full justify-center md:w-1/2">
              <div
                className="absolute inset-6 rounded-full bg-gradient-to-tl from-transparent via-[#FCD116] to-[#CE1126] opacity-80 animate-pulse"
                aria-hidden
              />
              <Image
                src="/brand/logo.png"
                alt="Smartmboa Tour"
                width={475}
                height={378}
                priority
                className="relative z-10 h-64 w-auto drop-shadow-xl sm:h-80"
              />
            </div>
          </div>
        </section>

        <section className="bg-gray-100 py-16">
          <div className="mx-auto max-w-6xl px-4 md:px-8">
            <h2 className="mb-8 text-center text-3xl font-bold text-[#007A5E] md:text-4xl">
              Ce que nous proposons
            </h2>
            <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
              {[
                {
                  icon: Compass,
                  title: 'Explorer une région',
                  body: 'Parcourez les dix régions et les lieux vérifiés de notre catalogue.',
                  href: '/explorer',
                },
                {
                  icon: MapPin,
                  title: 'Planifier un voyage',
                  body: 'Itinéraire, budget et hébergements à partir des données disponibles.',
                  href: '/planifier',
                },
                {
                  icon: Sparkles,
                  title: 'Demander au guide',
                  body: 'Posez une question en texte ou à la voix. La réponse reste ancrée dans les sources.',
                  href: '/assistant',
                },
              ].map((card) => (
                <Link
                  key={card.href}
                  href={card.href}
                  className="rounded-lg bg-white p-6 text-center shadow-lg transition duration-300 hover:scale-105"
                >
                  <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#FCD116]/40">
                    <card.icon className="h-7 w-7 text-[#007A5E]" aria-hidden />
                  </span>
                  <h3 className="mb-2 text-xl font-bold text-[#007A5E]">{card.title}</h3>
                  <p className="text-sm text-[#535557]">{card.body}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white py-16">
          <div className="mx-auto max-w-3xl px-4 text-center md:px-8">
            <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#CE1126]/10">
              <MapPin className="h-7 w-7 text-[#CE1126]" aria-hidden />
            </span>
            <h2 className="mb-4 text-3xl font-bold text-[#007A5E] lg:text-4xl">
              Choisissez une région
            </h2>
            <p className="mx-auto mb-8 max-w-2xl text-lg text-[#535557]">
              De Yaoundé à Maroua, chaque région a sa personnalité.
            </p>
            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-lg sm:p-8">
              <div className="flex flex-wrap justify-center gap-2">
                {REGIONS.map((region) => (
                  <Link
                    key={region.id}
                    href="/explorer"
                    className="rounded-full border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-[#007A5E] hover:text-[#007A5E]"
                  >
                    {region.nameFr}
                    {counts[region.id] ? ` · ${counts[region.id]}` : ''}
                  </Link>
                ))}
              </div>
              <Link
                href="/explorer"
                className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-[#007A5E] py-3 font-semibold text-white hover:bg-[#00614b]"
              >
                Tout explorer
              </Link>
            </div>
          </div>
        </section>

        <section className="bg-gray-100 py-16">
          <div className="mx-auto grid max-w-6xl items-center gap-8 px-4 md:grid-cols-2 md:px-8 lg:gap-12">
            <div className="relative overflow-hidden rounded-xl bg-gray-200 shadow-lg">
              <Image
                src="/regions/littoral.jpg"
                alt="Littoral, Cameroun"
                width={960}
                height={720}
                className="h-72 w-full object-cover md:h-96"
              />
            </div>
            <div>
              <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#FCD116]/40">
                <Camera className="h-7 w-7 text-[#007A5E]" aria-hidden />
              </span>
              <h2 className="mb-4 text-3xl font-bold text-[#373839] lg:text-4xl">
                Votre guide, où que vous soyez
              </h2>
              <p className="mb-8 text-lg leading-relaxed text-[#535557]">
                Loin de Douala ou de Yaoundé ? {APP_NAME} répond depuis le navigateur, avec les lieux déjà présents dans la base.
              </p>
              <ul className="space-y-4">
                {[
                  'Questions en texte ou à la voix',
                  'Photos de lieux pour les identifier',
                  'Itinéraires construits à partir du catalogue',
                ].map((item) => (
                  <li key={item} className="flex items-start gap-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#007A5E]/10">
                      <ArrowRight className="h-5 w-5 text-[#007A5E]" aria-hidden />
                    </span>
                    <span className="pt-1.5 text-[#373839]">{item}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-8 flex flex-col gap-4 sm:flex-row">
                <Link
                  href="/assistant"
                  className="rounded-full bg-[#007A5E] px-6 py-3 text-center font-semibold text-white hover:bg-[#00614b]"
                >
                  Commencer
                </Link>
                <Link
                  href="/culture"
                  className="rounded-full border-2 border-[#CE1126] px-6 py-3 text-center font-semibold text-[#CE1126] hover:bg-[#CE1126] hover:text-white"
                >
                  En savoir plus
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-[#007A5E] px-4 py-16 text-white md:px-8">
          <h2 className="mb-3 text-center text-3xl font-bold md:text-4xl">Le Cameroun, en chiffres</h2>
          <p className="mx-auto mb-12 max-w-lg text-center text-white/80">
            Un pays, dix régions, un guide pour s&apos;y retrouver.
          </p>
          <div className="mx-auto grid max-w-5xl grid-cols-1 gap-8 sm:grid-cols-3">
            {[
              ['10', 'régions à explorer'],
              [loadingPlaces ? '—' : String(allPlaces.length || '—'), 'lieux dans le catalogue'],
              ['1', 'assistant pour tout le pays'],
            ].map(([value, label]) => (
              <div key={label} className="flex flex-col items-center space-y-3 text-center">
                <p className="text-4xl font-bold text-[#FCD116] md:text-6xl">{value}</p>
                <div className="mb-1 h-1 w-20 bg-[#CE1126]" />
                <p className="text-sm md:text-lg">{label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Destinations populaires — catalogue style */}
        <section className="mx-auto max-w-6xl px-4 py-12 md:px-6">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gold)]">
                Destinations populaires
              </p>
              <h2 className="mt-1 font-display text-3xl font-bold text-[var(--green-deep)]">
                Les incontournables
              </h2>
              <p className="mt-2 text-[var(--muted)]">
                Sites vérifiés dans la base SmartMboa — photos Wikimedia / sources exportées.
              </p>
            </div>
            <Button href="/explorer" variant="outline" className="hidden sm:inline-flex">
              Tout explorer
            </Button>
          </div>

          <div className="mt-6 flex gap-4 overflow-x-auto no-scrollbar pb-2 snap-x">
            {loadingPlaces
              ? Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-72 w-72 shrink-0" />
                ))
              : mustSee.map((site) => (
                  <PlaceCard key={site.id} site={site} featured />
                ))}
          </div>
        </section>

        {/* Expériences */}
        <section className="bg-[var(--mint-soft)]/70 py-14">
          <div className="mx-auto max-w-6xl px-4 md:px-6">
            <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
              Expériences incontournables
            </h2>
            <p className="mt-2 text-[var(--muted)]">
              Nature, patrimoine et culture — uniquement des lieux présents dans notre catalogue.
            </p>
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {loadingPlaces
                ? Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-72 w-full" />
                  ))
                : experiences.map((site) => <PlaceCard key={site.id} site={site} />)}
            </div>
            {!loadingPlaces && experiences.length === 0 ? (
              <p className="mt-6 text-sm text-[var(--muted)]">
                Les expériences se chargeront dès que l&apos;API sera disponible.
              </p>
            ) : null}
          </div>
        </section>

        {/* 10 régions */}
        <section className="mx-auto max-w-6xl px-4 py-14 md:px-6">
          <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
            Explorer les 10 régions
          </h2>
          <p className="mt-2 text-[var(--muted)]">
            De Yaoundé à Maroua, chaque région a sa personnalité.
          </p>
          <div className="mt-8">
            <RegionCoverGrid counts={counts} />
          </div>
        </section>

        {/* Capabilities */}
        <section className="mx-auto max-w-6xl px-4 pb-14 md:px-6">
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
