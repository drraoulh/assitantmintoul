'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';

import { Button, ErrorState } from '@/components/ui';
import { friendlyError, identifyImage, sendChatMessage } from '@/lib/api/client';
import { useLocale } from '@/lib/i18n';

export default function VisionPage() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [guide, setGuide] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onFile(f: File | null) {
    setFile(f);
    setDescription(null);
    setGuide(null);
    setError(null);
    if (f) {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const vision = await identifyImage(file);
      setDescription(vision.description);
      const prompt =
        locale === 'fr'
          ? `À partir de cette description d'image, identifie le lieu touristique camerounais s'il est vérifié dans la base et donne des infos utiles : ${vision.description}`
          : `From this image description, identify the Cameroon tourist place if verified in the knowledge base and give useful info: ${vision.description}`;
      const chat = await sendChatMessage({ message: prompt, locale });
      setGuide(chat.message);
    } catch (err) {
      setError(friendlyError(err));
      setDescription(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
      <h1 className="font-display text-4xl text-[var(--green-deep)]">{t('vision.title')}</h1>
      <p className="mt-2 text-[var(--muted)]">
        Upload → Gemini Vision → Agents SmartMboa (aucune invention côté front).
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-3xl border border-[var(--line)] bg-white p-6">
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Aperçu" className="max-h-80 rounded-2xl object-contain" />
        ) : null}
        <Button type="submit" disabled={!file || loading}>
          {loading ? t('assistant.thinking') : t('vision.cta')}
        </Button>
      </form>

      {error ? (
        <div className="mt-6 space-y-2">
          <ErrorState message={error} />
          <p className="text-sm text-[var(--muted)]">{t('vision.fail')}</p>
        </div>
      ) : null}

      {description ? (
        <div className="mt-8 space-y-4">
          <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
            <h2 className="font-display text-xl text-[var(--green-deep)]">Identification</h2>
            <p className="mt-2 whitespace-pre-wrap">{description}</p>
          </section>
          {guide ? (
            <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
              <h2 className="font-display text-xl text-[var(--green-deep)]">Guide</h2>
              <p className="mt-2 whitespace-pre-wrap">{guide}</p>
              <div className="mt-4">
                <Button type="button" variant="secondary" onClick={() => router.push('/assistant')}>
                  Continuer avec l’assistant
                </Button>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
