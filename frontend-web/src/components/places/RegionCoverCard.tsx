'use client';

import Image from 'next/image';
import Link from 'next/link';

import { REGIONS, type RegionMeta } from '@/lib/regions';

export function RegionCoverCard({
  region,
  count,
  locale = 'fr',
  active = false,
  href,
  onClick,
}: {
  region: RegionMeta;
  count?: number;
  locale?: 'fr' | 'en';
  active?: boolean;
  href?: string;
  onClick?: () => void;
}) {
  const name = locale === 'fr' ? region.nameFr : region.nameEn;
  const capital = locale === 'fr' ? region.capitalFr : region.capitalEn;
  const className = `group relative block overflow-hidden rounded-2xl border text-left transition hover:-translate-y-0.5 ${
    active
      ? 'border-[var(--gold)] ring-1 ring-[var(--gold)]/40'
      : 'border-[var(--line)]'
  }`;

  const body = (
    <>
      <div className="relative aspect-[5/3] bg-[var(--green-deep)]">
        <Image
          src={region.coverImage}
          alt={`Région ${name}`}
          fill
          className="object-cover transition duration-500 group-hover:scale-[1.04]"
          sizes="(max-width:768px) 50vw, 20vw"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/15 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-3 text-white">
          <p className="font-semibold leading-tight">{name}</p>
          <p className="mt-0.5 text-xs text-white/80">
            {capital}
            {typeof count === 'number' && count > 0 ? ` · ${count} lieux` : ''}
          </p>
        </div>
      </div>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {body}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={`w-full ${className}`}>
      {body}
    </button>
  );
}

export function RegionCoverGrid({
  counts,
  locale = 'fr',
}: {
  counts?: Record<string, number>;
  locale?: 'fr' | 'en';
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {REGIONS.map((r) => (
        <RegionCoverCard
          key={r.id}
          region={r}
          count={counts?.[r.id]}
          locale={locale}
          href={`/destinations?region=${encodeURIComponent(r.apiRegion)}`}
        />
      ))}
    </div>
  );
}
