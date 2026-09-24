import { Suspense } from 'react';

import { AssistantPageClient } from '@/components/assistant/AssistantChat';
import { Skeleton } from '@/components/ui';

export default function AssistantPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 md:px-6">
      <Suspense fallback={<Skeleton className="h-[70vh] w-full" />}>
        <AssistantPageClient />
      </Suspense>
    </div>
  );
}
