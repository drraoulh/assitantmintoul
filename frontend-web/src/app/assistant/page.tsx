import { Suspense } from 'react';

import { AssistantPageClient } from '@/components/assistant/AssistantChat';
import { PageTransition } from '@/components/motion';
import { Skeleton } from '@/components/ui';

export default function AssistantPage() {
  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-0 py-0 md:px-6 md:py-8">
        <Suspense fallback={<Skeleton className="h-[70vh] w-full" />}>
          <AssistantPageClient />
        </Suspense>
      </div>
    </PageTransition>
  );
}
