'use client';

import { FormEvent, useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Camera, Upload } from 'lucide-react';

import { PageTransition } from '@/components/motion';
import { Button, ErrorState, ThinkingDots } from '@/components/ui';
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
  const [dragging, setDragging] = useState(false);

  const onFile = useCallback((f: File | null) => {
    setFile(f);
    setDescription(null);
    setGuide(null);
    setError(null);
    if (f) {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null);
    }
  }, []);

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
    <PageTransition>
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <h1 className="font-display text-4xl font-bold text-[var(--green-deep)]">
          {t('vision.title')}
        </h1>
        <p className="mt-2 text-[var(--muted)]">Montrez-moi ce que vous voyez.</p>

        <form
          onSubmit={onSubmit}
          className="mt-8 space-y-4 rounded-3xl border border-[var(--line)] bg-white p-6 shadow-[var(--shadow-soft)]"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
        >
          <div
            className={`flex flex-col items-center justify-center rounded-2xl border border-dashed px-6 py-12 text-center transition ${
              dragging
                ? 'border-[var(--gold)] bg-[var(--mint-soft)]'
                : 'border-[var(--line)] bg-[var(--ivory)]'
            }`}
          >
            <Camera className="h-10 w-10 text-[var(--green)]" aria-hidden />
            <p className="mt-3 font-semibold text-[var(--green-deep)]">
              Prendre une photo ou importer une image
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Glissez-déposez sur ordinateur, ou choisissez un fichier.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-[var(--green-deep)] px-4 py-2 text-sm font-semibold text-white">
                <Upload className="h-4 w-4" aria-hidden />
                Choisir une image
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => onFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </div>

          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview}
              alt="Aperçu de la photo à analyser"
              className="max-h-80 w-full rounded-2xl object-contain"
            />
          ) : null}

          <Button type="submit" disabled={!file || loading} size="lg">
            {loading ? t('assistant.thinking') : t('vision.cta')}
          </Button>
        </form>

        {loading ? (
          <div className="mt-6">
            <ThinkingDots label="Analyse de l’image…" />
          </div>
        ) : null}

        {error ? (
          <div className="mt-6 space-y-2">
            <ErrorState message={error} />
            <p className="text-sm text-[var(--muted)]">{t('vision.fail')}</p>
          </div>
        ) : null}

        {description ? (
          <div className="mt-8 space-y-4">
            <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
              <h2 className="font-display text-xl font-semibold text-[var(--green-deep)]">
                Identification
              </h2>
              <p className="mt-2 whitespace-pre-wrap">{description}</p>
            </section>
            {guide ? (
              <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
                <h2 className="font-display text-xl font-semibold text-[var(--green-deep)]">
                  Guide
                </h2>
                <p className="mt-2 whitespace-pre-wrap">{guide}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => router.push('/assistant')}
                  >
                    Continuer avec l’assistant
                  </Button>
                  <Button href="/mon-voyage" variant="outline">
                    Ajouter à mon voyage
                  </Button>
                </div>
              </section>
            ) : null}
          </div>
        ) : null}
      </div>
    </PageTransition>
  );
}
