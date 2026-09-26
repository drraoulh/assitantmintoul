'use client';

import { useState } from 'react';
import { Languages } from 'lucide-react';

import { LanguageGameModal } from '@/components/languages/LanguageGameModal';
import { useLocale } from '@/lib/i18n';

export default function LanguesPage() {
  const { locale } = useLocale();
  const fr = locale === 'fr';
  const [open, setOpen] = useState(true);

  return (
    <div className="mx-auto max-w-3xl px-4 py-14 md:px-8">
      <LanguageGameModal open={open} onClose={() => setOpen(false)} />
      <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#FCD116]/40">
        <Languages className="h-7 w-7 text-[#007A5E]" aria-hidden />
      </span>
      <h1 className="text-3xl font-bold text-[#007A5E] md:text-4xl">
        {fr ? 'Parler local' : 'Speak local'}
      </h1>
      <p className="mt-3 max-w-xl text-lg text-[#535557]">
        {fr
          ? 'Apprenez les salutations et phrases utiles en Ewondo, Duala, Fulfulde et Yemba — pour voyager avec respect.'
          : 'Learn useful greetings and phrases in Ewondo, Duala, Fulfulde and Yemba — travel with respect.'}
      </p>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-8 rounded-full bg-[#007A5E] px-8 py-3 text-base font-bold text-white shadow-md hover:bg-[#00614b]"
      >
        {fr ? 'Lancer le quiz' : 'Start the quiz'}
      </button>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2">
        {[
          { name: 'Ewondo', tag: fr ? 'Fang-Beti · Centre' : 'Fang-Beti · Centre' },
          { name: 'Duala', tag: fr ? 'Sawa · Littoral' : 'Sawa · Littoral' },
          { name: 'Fulfulde', tag: fr ? 'Nord · Sahel' : 'North · Sahel' },
          { name: 'Yemba', tag: fr ? 'Grassfields · Ouest' : 'Grassfields · West' },
        ].map((lang) => (
          <li
            key={lang.name}
            className="rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm"
          >
            <p className="font-bold text-[#007A5E]">{lang.name}</p>
            <p className="text-sm text-[#535557]">{lang.tag}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
