'use client';

import { PlaceCard } from '@/components/places/PlaceCard';
import { TourismMap } from '@/components/maps/TourismMap';
import { Badge } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import type { ChatSource, MapMarker, ResponseKind } from '@/lib/types';

export function ResponseRenderer({
  text,
  kind,
  sources,
  markers,
}: {
  text: string;
  kind: ResponseKind;
  sources?: ChatSource[];
  markers?: MapMarker[];
}) {
  const { t } = useLocale();
  const hasWeb =
    sources?.some((s) => Boolean(s.url)) ||
    /http|www\.|source/i.test(text);

  return (
    <div className="space-y-4">
      <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-[var(--ink)]">
        {text}
      </div>

      {hasWeb ? (
        <Badge tone="yellow">{t('web.verified')}</Badge>
      ) : null}

      {sources && sources.length > 0 && (kind === 'PLACE_SEARCH' || kind === 'PLACE_DETAILS' || kind === 'HOTEL') ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sources.map((s, i) => (
            <PlaceCard
              key={`${s.title}-${i}`}
              site={{
                id: encodeURIComponent(s.title),
                name: s.title,
                city: s.city,
                region: s.region,
                category: s.category,
                image_url: s.image_url,
              }}
              href={
                s.url?.startsWith('http')
                  ? undefined
                  : `/destinations?q=${encodeURIComponent(s.title)}`
              }
            />
          ))}
        </div>
      ) : null}

      {markers && markers.length > 0 ? (
        <TourismMap markers={markers} className="h-72" />
      ) : null}

      {sources?.some((s) => s.url) ? (
        <div>
          <p className="mb-2 text-sm font-semibold text-[var(--green-deep)]">
            {t('sources.title')}
          </p>
          <ul className="space-y-1 text-sm">
            {sources
              .filter((s) => s.url)
              .map((s, i) => (
                <li key={`${s.url}-${i}`}>
                  <a
                    href={s.url!}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[var(--green)] underline"
                  >
                    {s.title || s.url}
                  </a>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function BudgetCard({
  lines,
}: {
  lines: { label: string; amount: string | null }[];
}) {
  const known = lines.filter((l) => l.amount);
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white p-5">
      <h3 className="font-display text-lg text-[var(--green-deep)]">Budget estimatif</h3>
      <ul className="mt-3 space-y-2 text-sm">
        {lines.map((l) => (
          <li key={l.label} className="flex justify-between gap-4">
            <span>{l.label}</span>
            <span className="font-medium">{l.amount ?? 'Non disponible'}</span>
          </li>
        ))}
      </ul>
      {known.length ? (
        <p className="mt-4 border-t border-[var(--line)] pt-3 text-sm text-[var(--muted)]">
          Seuls les montants fournis par le backend sont affichés.
        </p>
      ) : null}
    </div>
  );
}
