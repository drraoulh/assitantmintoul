'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

import { BudgetCard } from '@/components/assistant/ResponseRenderer';
import { Button, Input, Select } from '@/components/ui';
import { friendlyError, sendChatMessage } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';
import { setTripMeta } from '@/lib/trip-store';

export default function PlanifierPage() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const [destination, setDestination] = useState('Bafoussam');
  const [days, setDays] = useState('3');
  const [travelers, setTravelers] = useState('2');
  const [budget, setBudget] = useState('150000');
  const [interests, setInterests] = useState('Culture + Nature');
  const [style, setStyle] = useState('Découverte');
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const prompt =
      locale === 'fr'
        ? `Je veux rester ${days} jours à ${destination} avec ${travelers} voyageurs et un budget de ${budget} FCFA. Centres d'intérêt : ${interests}. Style : ${style}. Propose un itinéraire vérifié.`
        : `I want to stay ${days} days in ${destination} with ${travelers} travelers and a budget of ${budget} FCFA. Interests: ${interests}. Style: ${style}. Propose a verified itinerary.`;
    try {
      const res = await sendChatMessage({ message: prompt, locale });
      setResult(res.message);
      setTripMeta({
        destination,
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
    <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
      <h1 className="font-display text-4xl text-[var(--green-deep)]">{t('planner.title')}</h1>
      <p className="mt-2 text-[var(--muted)]">
        Les réponses viennent de l’orchestrateur (Agents 1–4) — aucune donnée inventée côté front.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-3xl border border-[var(--line)] bg-white p-6">
        <label className="block text-sm font-medium">
          Destination
          <Input className="mt-1" value={destination} onChange={(e) => setDestination(e.target.value)} />
        </label>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block text-sm font-medium">
            Durée (jours)
            <Input className="mt-1" value={days} onChange={(e) => setDays(e.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Voyageurs
            <Input className="mt-1" value={travelers} onChange={(e) => setTravelers(e.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Budget (FCFA)
            <Input className="mt-1" value={budget} onChange={(e) => setBudget(e.target.value)} />
          </label>
        </div>
        <label className="block text-sm font-medium">
          Centres d’intérêt
          <Input className="mt-1" value={interests} onChange={(e) => setInterests(e.target.value)} />
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
        <Button type="submit" disabled={loading}>
          {loading ? t('assistant.thinking') : t('planner.cta')}
        </Button>
      </form>

      {error ? <p className="mt-4 text-sm text-[var(--red)]">{error}</p> : null}

      {result ? (
        <div className="mt-8 space-y-6">
          <div className="rounded-3xl border border-[var(--line)] bg-white p-6">
            <h2 className="font-display text-2xl text-[var(--green-deep)]">Votre voyage</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {destination} · {days} jours · {travelers} voyageurs · {budget} FCFA
            </p>
            <div className="mt-4 whitespace-pre-wrap leading-relaxed">{result}</div>
            <div className="mt-4">
              <Button type="button" variant="secondary" onClick={() => router.push('/mon-voyage')}>
                Voir sur Mon voyage
              </Button>
            </div>
          </div>
          <BudgetCard
            lines={[
              { label: 'Budget déclaré', amount: `${budget} FCFA` },
              { label: 'Hébergement', amount: null },
              { label: 'Activités', amount: null },
              { label: 'Transport', amount: null },
            ]}
          />
        </div>
      ) : null}
    </div>
  );
}
