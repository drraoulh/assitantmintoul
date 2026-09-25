'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Landmark, Mountain, Trees, Waves } from 'lucide-react';

import { PageTransition, SlideUp } from '@/components/motion';
import { Button } from '@/components/ui';

/**
 * Cultural areas of Cameroon — high-level public geography/anthropology framing.
 * Short original copy; not scraped from third-party sites.
 */
const AREAS = [
  {
    id: 'soudano-sahelien',
    title: 'Aire soudano-sahélienne',
    regions: 'Extrême-Nord, Nord, Adamaoua',
    icon: Mountain,
    body: 'Savanes, montagnes Mandara, parcs animaliers et architectures vernaculaires du Nord.',
    href: '/destinations?region=Extr%C3%AAme-Nord',
    image: '/regions/extreme-nord.jpg',
  },
  {
    id: 'grassfields',
    title: 'Grassfields',
    regions: 'Ouest, Nord-Ouest',
    icon: Landmark,
    body: 'Chefferies, palais royaux, artisanat et hauts plateaux des Grassfields.',
    href: '/destinations?region=Ouest',
    image: '/regions/ouest.jpg',
  },
  {
    id: 'fang-beti',
    title: 'Aire Fang-Beti',
    regions: 'Centre, Sud, Est',
    icon: Trees,
    body: 'Forêts équatoriales, patrimoine urbain de Yaoundé et réserves de faune de l’Est.',
    href: '/destinations?region=Centre',
    image: '/regions/centre.jpg',
  },
  {
    id: 'sawa',
    title: 'Aire Sawa',
    regions: 'Littoral, Sud-Ouest',
    icon: Waves,
    body: 'Côte atlantique, Limbé, Douala et traditions côtières face à l’océan.',
    href: '/destinations?region=Littoral',
    image: '/regions/littoral.jpg',
  },
] as const;

const TIMELINE = [
  {
    title: 'Royaumes et chefferies',
    body: 'Avant la colonisation, le territoire accueillait des structures politiques variées — royaumes, lamidats et chefferies toujours visibles dans le paysage culturel.',
  },
  {
    title: 'Kamerun allemand',
    body: 'Le protectorat allemand (fin XIXe – 1916) a laissé des traces urbaines et infrastructurelles, notamment sur la côte et dans les montagnes de l’Ouest.',
  },
  {
    title: 'Mandats franco-britanniques',
    body: 'Après 1916, le territoire est administré sous mandats français et britanniques — une dualité encore perceptible dans les langues et les institutions.',
  },
  {
    title: 'Indépendance et Réunification',
    body: 'Indépendance du Cameroun sous administration française (1960), puis réunification avec le Cameroun méridional britannique (1961) — l’« Afrique en miniature » moderne.',
  },
] as const;

export default function CulturePage() {
  return (
    <PageTransition>
      <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
        <SlideUp>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gold)]">
            Culture & histoire
          </p>
          <h1 className="mt-2 font-display text-4xl font-bold text-[var(--green-deep)]">
            Quatre grandes aires culturelles
          </h1>
          <p className="mt-3 max-w-2xl text-[var(--muted)]">
            Un pays, plusieurs mondes. Explorez les régions liées à chaque aire, puis
            demandez à SmartMboa des détails vérifiés sur les lieux et traditions.
          </p>
        </SlideUp>

        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          {AREAS.map((area) => (
            <Link
              key={area.id}
              href={area.href}
              className="group overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-[var(--shadow-soft)] transition hover:-translate-y-0.5"
            >
              <div className="relative aspect-[16/9] bg-[var(--green-deep)]">
                <Image
                  src={area.image}
                  alt={area.title}
                  fill
                  className="object-cover transition duration-500 group-hover:scale-[1.03]"
                  sizes="(max-width:768px) 100vw, 50vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                <div className="absolute bottom-0 p-5 text-white">
                  <area.icon className="mb-2 h-5 w-5 text-[var(--gold)]" aria-hidden />
                  <h2 className="font-display text-xl font-semibold">{area.title}</h2>
                  <p className="mt-1 text-xs text-white/75">{area.regions}</p>
                </div>
              </div>
              <p className="p-5 text-sm text-[var(--muted)]">{area.body}</p>
            </Link>
          ))}
        </div>

        <section className="mt-16">
          <h2 className="font-display text-3xl font-bold text-[var(--green-deep)]">
            Repères historiques
          </h2>
          <p className="mt-2 text-[var(--muted)]">
            Synthèse pédagogique — pour des fiches lieu par lieu, utilisez l’assistant.
          </p>
          <ol className="mt-8 space-y-4">
            {TIMELINE.map((item, i) => (
              <li
                key={item.title}
                className="rounded-2xl border border-[var(--line)] bg-white px-5 py-4"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--gold)]">
                  {i + 1}. {item.title}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-[var(--ink)]">{item.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <div className="mt-12 flex flex-wrap gap-3">
          <Button href="/assistant?q=Parle-moi%20de%20la%20culture%20et%20des%20chefferies%20au%20Cameroun">
            Demander à SmartMboa
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
          <Button href="/explorer" variant="outline">
            Explorer les régions
          </Button>
        </div>
      </div>
    </PageTransition>
  );
}
