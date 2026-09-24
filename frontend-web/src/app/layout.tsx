import type { Metadata } from 'next';
import { Fraunces, Source_Sans_3 } from 'next/font/google';

import { SiteFooter } from '@/components/layout/SiteHeader';
import { SiteHeader } from '@/components/layout/SiteHeader';
import { LocaleProvider } from '@/lib/i18n';
import { APP_NAME } from '@/lib/config';

import './globals.css';

const display = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

const body = Source_Sans_3({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: `${APP_NAME} — Découvrez le Cameroun avec l'IA`,
    template: `%s · ${APP_NAME}`,
  },
  description:
    'Plateforme touristique intelligente du Cameroun : destinations vérifiées, assistant IA, vision, voix et planification.',
  openGraph: {
    title: `${APP_NAME} — Découvrez le Cameroun avec l'IA`,
    description:
      'Explorez les régions, planifiez un voyage et parlez à l’assistant SmartMboa.',
    type: 'website',
    locale: 'fr_CM',
  },
  icons: {
    icon: '/favicon.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className={`${display.variable} ${body.variable} antialiased`}>
        <LocaleProvider>
          <div className="flex min-h-screen flex-col">
            <SiteHeader />
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </div>
        </LocaleProvider>
      </body>
    </html>
  );
}
