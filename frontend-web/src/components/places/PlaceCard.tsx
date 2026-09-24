'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';

import { Badge, Button } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { addPlaceToTrip } from '@/lib/trip-store';
import type { TouristSite } from '@/lib/types';

export function PlaceCard({
  site,
  href,
}: {
  site: TouristSite | {
    id: string;
    name: string;
    city?: string | null;
    region?: string | null;
    category?: string | null;
    description?: string;
    images?: string[];
    image_url?: string | null;
    latitude?: number | null;
    longitude?: number | null;
  };
  href?: string;
}) {
  const { t } = useLocale();
  const [added, setAdded] = useState(false);
  const image =
    ('images' in site && site.images?.[0]) ||
    ('image_url' in site && site.image_url) ||
    null;
  const link = href ?? `/destinations/${encodeURIComponent(site.id)}`;

  return (
    <article className="overflow-hidden rounded-2xl border border-[var(--line)] bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <Link href={link} className="block">
        <div className="relative aspect-[16/10] bg-gradient-to-br from-[var(--green-deep)] via-[var(--green)] to-[var(--yellow)]/40">
          {image ? (
            <Image
              src={image}
              alt={site.name}
              fill
              className="object-cover"
              sizes="(max-width:768px) 100vw, 33vw"
              unoptimized
            />
          ) : (
            <div className="absolute inset-0 flex items-end p-4">
              <span className="font-display text-2xl text-white/90">{site.name.slice(0, 1)}</span>
            </div>
          )}
        </div>
      </Link>
      <div className="space-y-3 p-4">
        <div>
          <h3 className="font-display text-lg text-[var(--green-deep)]">{site.name}</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            📍 {[site.city, site.region].filter(Boolean).join(', ')}
          </p>
        </div>
        {site.category ? <Badge>{site.category}</Badge> : null}
        <div className="flex flex-wrap gap-2">
          <Button href={link} size="sm" variant="secondary">
            {t('place.discover')} →
          </Button>
          <Button
            size="sm"
            variant="primary"
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
    </article>
  );
}
