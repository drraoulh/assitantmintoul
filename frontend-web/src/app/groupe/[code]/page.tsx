'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';

import { getDeviceId, rememberName, savedName } from '@/lib/groups/device';
import type { GroupMessage, GroupSummary } from '@/lib/groups/types';

export default function GroupRoomPage({ params }: { params: Promise<{ code: string }> }) {
  const [code, setCode] = useState('');
  const [group, setGroup] = useState<GroupSummary | null>(null);
  const [missing, setMissing] = useState(false);
  const [name, setName] = useState('');
  const [joined, setJoined] = useState(false);
  const [messages, setMessages] = useState<GroupMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [deviceId, setDeviceId] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void params.then(async ({ code: raw }) => {
      const next = raw.toUpperCase();
      setCode(next);
      setDeviceId(getDeviceId());
      const known = savedName(next);
      if (known) setName(known);
      const response = await fetch(`/api/groups/${next}`);
      if (cancelled) return;
      if (!response.ok) {
        setMissing(true);
        return;
      }
      setGroup((await response.json()) as GroupSummary);
      if (!known) return;
      const join = await fetch(`/api/groups/${next}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deviceId: getDeviceId(), name: known }),
      });
      if (!cancelled && join.ok) setJoined(true);
    });
    return () => {
      cancelled = true;
    };
  }, [params]);

  const loadMessages = useCallback(async () => {
    if (!code || !joined) return;
    const response = await fetch(`/api/groups/${code}/messages`);
    if (!response.ok) return;
    const payload = (await response.json()) as { messages: GroupMessage[] };
    setMessages(payload.messages);
  }, [code, joined]);

  useEffect(() => {
    if (!joined) return;
    void loadMessages();
    const timer = window.setInterval(() => void loadMessages(), 2000);
    return () => window.clearInterval(timer);
  }, [joined, loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function enter(event: FormEvent) {
    event.preventDefault();
    setError('');
    const response = await fetch(`/api/groups/${code}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId, name }),
    });
    const payload = (await response.json()) as { error?: string };
    if (!response.ok) {
      setError(payload.error || 'Impossible de rejoindre.');
      return;
    }
    rememberName(code, name.trim());
    setJoined(true);
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    const response = await fetch(`/api/groups/${code}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deviceId, text }),
    });
    if (!response.ok) {
      setDraft(text);
      return;
    }
    const message = (await response.json()) as GroupMessage;
    setMessages((current) =>
      current.some((item) => item.id === message.id) ? current : [...current, message],
    );
  }

  async function copyLink() {
    const url = `${window.location.origin}/groupe/${code}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  if (missing) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-[#007A5E]">Groupe introuvable</h1>
        <p className="mt-3 text-[#535557]">Vérifiez le code, ou créez un nouveau salon.</p>
        <Link href="/groupe" className="mt-6 inline-block rounded-full bg-[#007A5E] px-6 py-3 font-bold text-white">
          Retour
        </Link>
      </div>
    );
  }

  if (!group) {
    return <p className="px-4 py-10 text-center text-[#535557]">Ouverture du groupe…</p>;
  }

  if (!joined) {
    return (
      <div className="mx-auto max-w-lg px-4 py-14">
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[#CE1126]">{code}</p>
        <h1 className="mt-2 text-3xl font-bold text-black">{group.name}</h1>
        <p className="mt-3 text-[#535557]">Choisissez le prénom que les autres verront. Pas de compte.</p>
        <form onSubmit={enter} className="mt-6 rounded-xl bg-white p-6 shadow-lg">
          <label className="text-sm font-semibold text-[#373839]" htmlFor="display-name">
            Prénom
          </label>
          <input
            id="display-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={24}
            required
            className="mt-2 w-full rounded-full border border-gray-200 px-4 py-3 outline-none focus:border-[#007A5E]"
            placeholder="Amina"
          />
          {error ? <p className="mt-3 text-sm text-[#CE1126]">{error}</p> : null}
          <button
            type="submit"
            className="mt-4 rounded-full bg-[#007A5E] px-6 py-3 text-sm font-bold text-white hover:bg-[#00614b]"
          >
            Entrer dans le groupe
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col bg-gray-100">
      <header className="flex shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4 py-3 md:px-6">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-bold text-[#007A5E]">{group.name}</h1>
          <p className="font-mono text-xs tracking-[0.18em] text-[#535557]">{code}</p>
        </div>
        <button
          type="button"
          onClick={() => void copyLink()}
          className="rounded-full bg-[#FCD116] px-4 py-2 text-sm font-bold text-[#1a1a1a]"
        >
          {copied ? 'Lien copié' : 'Copier le lien'}
        </button>
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4 md:px-6">
        {messages.length === 0 ? (
          <p className="py-8 text-center text-sm text-[#535557]">
            Le salon est ouvert. Dites bonjour au groupe.
          </p>
        ) : null}
        {messages.map((message) => {
          const mine = message.memberId === deviceId;
          return (
            <div key={message.id} className={mine ? 'ml-auto max-w-[80%]' : 'mr-auto max-w-[80%]'}>
              {!mine ? (
                <p className="mb-1 text-xs font-bold" style={{ color: message.color }}>
                  {message.name}
                </p>
              ) : null}
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm ${
                  mine ? 'bg-[#007A5E] text-white' : 'bg-white text-[#1a1a1a] shadow-md'
                }`}
              >
                {message.text}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(event) => void send(event)}
        className="shrink-0 bg-white p-3 md:p-4"
      >
        <div className="mx-auto flex max-w-3xl items-center gap-2 rounded-full border border-gray-200 bg-white p-2 shadow-lg">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={500}
            placeholder="Écrire au groupe…"
            className="min-w-0 flex-1 border-0 px-3 py-2 outline-none"
            aria-label="Message"
          />
          <button
            type="submit"
            className="rounded-full bg-[#007A5E] px-5 py-2 text-sm font-bold text-white hover:bg-[#00614b]"
          >
            Envoyer
          </button>
        </div>
      </form>
    </div>
  );
}
