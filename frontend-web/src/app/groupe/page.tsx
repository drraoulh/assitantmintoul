'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Users } from 'lucide-react';

export default function GroupLobbyPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function createGroup(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      const payload = (await response.json()) as { code?: string; error?: string };
      if (!response.ok || !payload.code) {
        setError(payload.error || 'Impossible de créer le groupe.');
        return;
      }
      router.push(`/groupe/${payload.code}`);
    } catch {
      setError('Impossible de créer le groupe.');
    } finally {
      setBusy(false);
    }
  }

  function joinGroup(event: FormEvent) {
    event.preventDefault();
    const next = code.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (next.length < 4) {
      setError('Entrez le code du groupe.');
      return;
    }
    router.push(`/groupe/${next}`);
  }

  return (
    <div className="bg-gray-100">
      <section className="mx-auto grid max-w-5xl gap-6 px-4 py-14 md:grid-cols-2 md:px-8">
        <div className="md:col-span-2">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#CE1126]">
            Sans compte
          </p>
          <h1 className="mt-2 text-3xl font-bold text-black md:text-4xl">
            Un groupe pour votre voyage
          </h1>
          <p className="mt-3 max-w-2xl text-lg text-[#535557]">
            Créez un salon, partagez le lien, et chacun choisit un prénom. Personne n’a besoin d’un compte.
          </p>
        </div>

        <form onSubmit={createGroup} className="rounded-xl bg-white p-6 shadow-lg">
          <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#FCD116]/50">
            <Users className="h-6 w-6 text-[#007A5E]" aria-hidden />
          </span>
          <h2 className="text-xl font-bold text-[#007A5E]">Créer un groupe</h2>
          <p className="mt-2 text-sm text-[#535557]">
            Par exemple « Limbé, 12–15 octobre ».
          </p>
          <label className="mt-5 block text-sm font-semibold text-[#373839]" htmlFor="group-name">
            Nom du groupe
          </label>
          <input
            id="group-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={60}
            required
            className="mt-2 w-full rounded-full border border-gray-200 px-4 py-3 outline-none focus:border-[#007A5E]"
            placeholder="Nom du voyage"
          />
          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded-full bg-[#007A5E] px-6 py-3 text-sm font-bold text-white hover:bg-[#00614b] disabled:opacity-60"
          >
            Créer et obtenir le lien
          </button>
        </form>

        <form onSubmit={joinGroup} className="rounded-xl bg-white p-6 shadow-lg">
          <h2 className="text-xl font-bold text-[#007A5E]">Rejoindre</h2>
          <p className="mt-2 text-sm text-[#535557]">
            Collez le code reçu de vos compagnons de voyage.
          </p>
          <label className="mt-5 block text-sm font-semibold text-[#373839]" htmlFor="group-code">
            Code
          </label>
          <input
            id="group-code"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            maxLength={12}
            className="mt-2 w-full rounded-full border border-gray-200 px-4 py-3 font-mono tracking-[0.2em] outline-none focus:border-[#007A5E]"
            placeholder="K7M2QX"
          />
          <button
            type="submit"
            className="mt-4 rounded-full border-2 border-[#CE1126] px-6 py-3 text-sm font-bold text-[#CE1126] hover:bg-[#CE1126] hover:text-white"
          >
            Entrer
          </button>
        </form>

        {error ? (
          <p className="md:col-span-2 text-sm font-medium text-[#CE1126]" role="alert">
            {error}
          </p>
        ) : null}
      </section>
    </div>
  );
}
