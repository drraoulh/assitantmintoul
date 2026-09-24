'use client';

import { Suspense } from 'react';

import DestinationsInner from './DestinationsInner';
import { Skeleton } from '@/components/ui';

export default function DestinationsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-12">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="mt-8 h-80 w-full" />
        </div>
      }
    >
      <DestinationsInner />
    </Suspense>
  );
}
