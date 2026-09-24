'use client';

import dynamic from 'next/dynamic';

import { Skeleton } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import type { MapMarker } from '@/lib/types';

const Inner = dynamic(
  () =>
    import('./TourismMapInner').then((m) => m.TourismMapInner),
  {
    ssr: false,
    loading: () => <MapSkeleton />,
  },
);

function MapSkeleton() {
  const { t } = useLocale();
  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--muted)]">{t('map.loading')}</p>
      <Skeleton className="h-80 w-full" />
    </div>
  );
}

export function TourismMap({
  markers,
  className,
}: {
  markers: MapMarker[];
  className?: string;
}) {
  return <Inner markers={markers} className={className} />;
}
