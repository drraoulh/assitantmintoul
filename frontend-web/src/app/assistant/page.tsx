import { PageTransition } from '@/components/motion';
import { AssistantChat } from '@/components/assistant/AssistantChat';

/**
 * Server page — pass searchParams as props (no useSearchParams bailout).
 * Chat UI consumes structured ChatResponse from Agents 1–4 (no Agent 5).
 */
type AssistantSearchParams = {
  q?: string;
  voice?: string;
};

export default async function AssistantPage({
  searchParams,
}: {
  searchParams: Promise<AssistantSearchParams>;
}) {
  const params = await searchParams;
  const initialQuestion = params.q?.trim() || undefined;
  const autoVoice = params.voice === '1';

  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-0 py-0 md:px-6 md:py-8">
        <AssistantChat initialQuestion={initialQuestion} autoVoice={autoVoice} />
      </div>
    </PageTransition>
  );
}
