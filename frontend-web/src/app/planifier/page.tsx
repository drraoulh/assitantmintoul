'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Calendar, MapPin, Users, Wallet } from 'lucide-react';

import { ResponseRenderer, BudgetCard } from '@/components/assistant/ResponseRenderer';
import { DestinationAutocomplete } from '@/components/planner/DestinationAutocomplete';
import { PageTransition } from '@/components/motion';
import { Button, Input, Select, ThinkingDots } from '@/components/ui';
import { friendlyError, sendChatMessage } from '@/lib/api/client';
import { resolveCameroonDestination } from '@/lib/cameroon-destinations';
import { useLocale } from '@/lib/i18n';
import { setTripMeta } from '@/lib/trip-store';
import { structuredFromChatResponse } from '@/lib/utils/response';
import type { ChatResponse } from '@/lib/types';

const STEPS = [
  'Destination',
  'Durée',
  'Voyageurs',
  'Budget',
  'Intérêts',
] as const;

export default function PlanifierPage() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [destination, setDestination] = useState('');
  const [destinationValid, setDestinationValid] = useState(false);
  const [days, setDays] = useState('3');
  const [travelers, setTravelers] = useState('2');
  const [budget, setBudget] = useState('150000');
  const [interests, setInterests] = useState('Culture + Nature');
  const [style, setStyle] = useState('Découverte');
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onGenerate(e?: FormEvent) {
    e?.preventDefault();
    const matched = resolveCameroonDestination(destination);
    if (!matched) {
      setError('Area not found in Cameroon, check spelling');
      setStep(0);
      return;
    }
    const destLabel = matched.name;
    setLoading(true);
    setError(null);
    const prompt =
      locale === 'fr'
        ? `Je veux rester ${days} jours à ${destLabel} avec ${travelers} voyageurs et un budget de ${budget} FCFA. Centres d'intérêt : ${interests}. Style : ${style}. Propose un itinéraire vérifié.`
        : `I want to stay ${days} days in ${destLabel} with ${travelers} travelers and a budget of ${budget} FCFA. Interests: ${interests}. Style: ${style}. Propose a verified itinerary.`;
    try {
      const res = await sendChatMessage({ message: prompt, locale });
      setResult(res);
      setTripMeta({
        destination: destLabel,
        dates: `${days} jours`,
        travelers: Number(travelers) || undefined,
        budgetFcfa: Number(budget) || undefined,
        interests: interests.split('+').map((s) => s.trim()).filter(Boolean),
        style,
        itineraryText: res.message,
      });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageTransition>
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <h1 className="font-display text-4xl font-bold text-[var(--green-deep)]">
          {t('planner.title')}
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          Un assistant de voyage en étapes — réponses fournies par les agents SmartMboa.
        </p>

        <ol className="mt-8 flex flex-wrap gap-2">
          {STEPS.map((label, i) => (
            <li key={label}>
              <button
                type="button"
                onClick={() => setStep(i)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
                  step === i
                    ? 'bg-[var(--green-deep)] text-white'
                    : 'bg-[var(--mint-soft)] text-[var(--muted)]'
                }`}
              >
                {i + 1}. {label}
              </button>
            </li>
          ))}
        </ol>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (step === 0) {
              const matched = resolveCameroonDestination(destination);
              if (!matched) {
                setError('Area not found in Cameroon, check spelling');
                return;
              }
              setDestination(matched.name);
              setError(null);
              setStep(1);
              return;
            }
            if (step < STEPS.length - 1) setStep((s) => s + 1);
            else void onGenerate();
          }}
          className="mt-8 space-y-5 rounded-3xl border border-[var(--line)] bg-white p-6 shadow-[var(--shadow-soft)]"
        >
          {step === 0 && (
            <label className="block text-sm font-medium">
              Destination
              <div className="mt-1">
                <DestinationAutocomplete
                  value={destination}
                  onChange={(v) => {
                    setDestination(v);
                    setError(null);
                  }}
                  onValidityChange={setDestinationValid}
                  locale={locale}
                  required
                />
              </div>
            </label>
          )}
          {step === 1 && (
            <label className="block text-sm font-medium">
              Durée (jours)
              <Input
                className="mt-1"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                required
              />
            </label>
          )}
          {step === 2 && (
            <label className="block text-sm font-medium">
              Voyageurs
              <Input
                className="mt-1"
                value={travelers}
                onChange={(e) => setTravelers(e.target.value)}
                required
              />
            </label>
          )}
          {step === 3 && (
            <label className="block text-sm font-medium">
              Budget (FCFA)
              <Input
                className="mt-1"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                required
              />
            </label>
          )}
          {step === 4 && (
            <>
              <label className="block text-sm font-medium">
                Centres d&apos;intérêt
                <Input
                  className="mt-1"
                  value={interests}
                  onChange={(e) => setInterests(e.target.value)}
                />
              </label>
              <label className="block text-sm font-medium">
                Style
                <Select className="mt-1" value={style} onChange={(e) => setStyle(e.target.value)}>
                  <option>Découverte</option>
                  <option>Nature</option>
                  <option>Culture</option>
                  <option>Famille</option>
                </Select>
              </label>
            </>
          )}

          <div className="flex flex-wrap gap-2">
            {step > 0 ? (
              <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
                Retour
              </Button>
            ) : null}
            <Button
              type="submit"
              disabled={
                loading ||
                (step === 0 && (!destination.trim() || !destinationValid))
              }
            >
              {step < STEPS.length - 1 ? (
                <>
                  Continuer <ArrowRight className="h-4 w-4" aria-hidden />
                </>
              ) : loading ? (
                t('assistant.thinking')
              ) : (
                'Générer mon voyage'
              )}
            </Button>
          </div>
        </form>

        {loading ? (
          <div className="mt-6">
            <ThinkingDots label="SmartMboa prépare votre itinéraire…" />
          </div>
        ) : null}
        {error ? <p className="mt-4 text-sm text-[var(--danger)]">{error}</p> : null}

        {result ? (
          <div className="mt-8 space-y-6">
            <div className="rounded-3xl border border-[var(--line)] bg-white p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gold)]">
                Votre voyage au Cameroun
              </p>
              <ul className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                <li className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-[var(--green)]" aria-hidden />
                  {destination}
                </li>
                <li className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-[var(--green)]" aria-hidden />
                  {days} jours
                </li>
                <li className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-[var(--green)]" aria-hidden />
                  {travelers} voyageurs
                </li>
                <li className="flex items-center gap-2">
                  <Wallet className="h-4 w-4 text-[var(--green)]" aria-hidden />
                  {budget} FCFA
                </li>
              </ul>
              <div className="my-5 h-px bg-[var(--line)]" />
              <ResponseRenderer
                text={result.message}
                ui={structuredFromChatResponse(result)}
              />
              <div className="mt-4">
                <Button type="button" variant="secondary" onClick={() => router.push('/mon-voyage')}>
                  Voir sur Mon voyage
                </Button>
              </div>
            </div>
            {!result.budget ? (
              <BudgetCard
                lines={[
                  { label: 'Budget déclaré', amount: `${budget} FCFA` },
                  { label: 'Hébergement', amount: null },
                  { label: 'Activités', amount: null },
                  { label: 'Transport', amount: null },
                ]}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </PageTransition>
  );
}
