'use client';

import { HomeAssistantTeaser } from '@/components/assistant/HomeAssistantTeaser';
import { Button } from '@/components/ui';
import { useLocale } from '@/lib/i18n';
import { APP_NAME } from '@/lib/config';

export default function HomePage() {
  const { t } = useLocale();

  return (
    <>
      <section className="relative isolate min-h-[88vh] overflow-hidden bg-[var(--green-deep)] text-[var(--ivory)]">
        <div
          className="absolute inset-0 opacity-90"
          style={{
            background:
              'radial-gradient(ellipse 80% 60% at 70% 20%, rgba(252,209,22,0.28), transparent 55%), radial-gradient(ellipse 70% 50% at 10% 80%, rgba(14,158,118,0.45), transparent 50%), linear-gradient(160deg, #00412F 0%, #007A5E 48%, #003526 100%)',
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.12]"
          style={{
            backgroundImage:
              'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'1\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
          }}
          aria-hidden
        />
        <div className="relative mx-auto flex min-h-[88vh] max-w-6xl flex-col justify-end px-4 pb-16 pt-28 md:justify-center md:px-6 md:pb-24">
          <p className="font-display text-4xl font-semibold tracking-tight md:text-6xl lg:text-7xl">
            {APP_NAME}
          </p>
          <h1 className="mt-4 max-w-3xl font-display text-3xl leading-tight md:text-5xl">
            {t('hero.title')}
            <span className="block text-[var(--yellow)]">{t('hero.sub')}</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg text-white/85">{t('hero.body')}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button href="/explorer" size="lg">
              {t('hero.ctaExplore')}
            </Button>
            <Button href="/planifier" size="lg" variant="ghost">
              {t('hero.ctaPlan')}
            </Button>
            <Button href="/assistant" size="lg" variant="secondary">
              {t('hero.ctaAssist')}
            </Button>
          </div>
        </div>
      </section>

      <HomeAssistantTeaser />

      <section className="mx-auto max-w-6xl px-4 pb-20 md:px-6">
        <div className="grid gap-8 md:grid-cols-3">
          {[
            {
              title: 'Explorer',
              body: 'Dix régions officielles et lieux issus de la base vérifiée.',
              href: '/explorer',
            },
            {
              title: 'Planifier',
              body: 'Itinéraires et budgets construits par les agents SmartMboa.',
              href: '/planifier',
            },
            {
              title: 'Voir & parler',
              body: 'Vision Gemini et voix streaming (Whisper → Qwen → Fish Audio).',
              href: '/vision',
            },
          ].map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="group border-t border-[var(--green)] pt-5 transition hover:border-[var(--yellow)]"
            >
              <h2 className="font-display text-2xl text-[var(--green-deep)] group-hover:text-[var(--green)]">
                {item.title}
              </h2>
              <p className="mt-2 text-[var(--muted)]">{item.body}</p>
            </a>
          ))}
        </div>
      </section>
    </>
  );
}
