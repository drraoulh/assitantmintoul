import { AssistantChat } from '@/components/assistant/AssistantChat';

/**
 * Server page — pass searchParams as props so we do NOT call useSearchParams().
 * That avoids Next.js `BAILOUT_TO_CLIENT_SIDE_RENDERING`, which previously left
 * production /assistant showing only the site header + footer until JS hydrated.
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
    <div className="mx-auto max-w-5xl px-4 py-10 md:px-6">
      <AssistantChat initialQuestion={initialQuestion} autoVoice={autoVoice} />
    </div>
  );
}
