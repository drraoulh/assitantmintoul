'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { MapPin } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';

import { Badge, Button } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { resolvePlaceImage } from '@/lib/place-images';
import { addPlaceToTrip } from '@/lib/trip-store';
import type { TouristSite } from '@/lib/types';

type PlaceLike =
  | TouristSite
  | {
      id: string;
      name: string;
      slug?: string | null;
      city?: string | null;
      region?: string | null;
      category?: string | null;
      description?: string | null;
      images?: string[];
      image_url?: string | null;
      latitude?: number | null;
      longitude?: number | null;
      estimated_cost_xaf?: number | null;
      price?: string | null;
    };

export function PlaceCard({
  site,
  href,
  featured = false,
}: {
  site: PlaceLike;
  href?: string;
  featured?: boolean;
}) {
  const { t } = useLocale();
  const reduce = useReducedMotion();
  const [added, setAdded] = useState(false);
  const image = resolvePlaceImage(site);
  const link = href ?? `/destinations/${encodeURIComponent(site.id)}`;
  const price =
    ('price' in site && site.price) ||
    ('estimated_cost_xaf' in site &&
      typeof site.estimated_cost_xaf === 'number' &&
      `${site.estimated_cost_xaf} FCFA`) ||
    null;

  return (
    <motion.article
      className={`overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-[var(--shadow-soft)] ${
        featured ? 'min-w-[16.5rem] snap-start sm:min-w-[18rem]' : ''
      }`}
      whileHover={reduce ? undefined : { y: -3, transition: { duration: 0.25 } }}
    >
      <Link href={link} className="block overflow-hidden">
        <div className="relative aspect-[16/10] bg-gradient-to-br from-[var(--green-deep)] via-[var(--green)] to-[var(--gold)]/30">
          {image ? (
            <Image
              src={image}
              alt={site.name}
              fill
              className="object-cover transition duration-500 hover:scale-[1.03]"
              sizes="(max-width:768px) 85vw, 33vw"
              unoptimized
            />
          ) : (
            <div className="absolute inset-0 flex items-end p-4">
              <span className="font-display text-3xl font-bold text-white/85">
                {site.name.slice(0, 1)}
              </span>
            </div>
          )}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/35 to-transparent" />
          {site.category ? (
            <span className="absolute left-3 top-3 rounded-full bg-black/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white backdrop-blur-sm">
              {site.category}
            </span>
          ) : null}
        </div>
      </Link>
      <div className="space-y-3 p-4">
        <div>
          <h3 className="font-display text-lg font-semibold text-[var(--green-deep)]">
            {site.name}
          </h3>
          <p className="mt-1 flex items-center gap-1 text-sm text-[var(--muted)]">
            <MapPin className="h-3.5 w-3.5" aria-hidden />
            {[site.city, site.region].filter(Boolean).join(', ') || 'Cameroun'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {price ? <Badge tone="gold">{price}</Badge> : null}
        </div>
        {'description' in site && site.description ? (
          <p className="line-clamp-2 text-sm text-[var(--muted)]">{site.description}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button href={link} size="sm" variant="secondary">
            {t('place.discover')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            type="button"
            onClick={() => {
              addPlaceToTrip({
                id: site.id,
                name: site.name,
                city: site.city ?? undefined,
                region: site.region ?? undefined,
                category: site.category ?? undefined,
                imageUrl: image,
                latitude: 'latitude' in site ? site.latitude : null,
                longitude: 'longitude' in site ? site.longitude : null,
              });
              setAdded(true);
            }}
          >
            {added ? t('place.added') : t('place.add')}
          </Button>
        </div>
      </div>
    </motion.article>
  );
}
