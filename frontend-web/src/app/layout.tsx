import type { Metadata } from 'next';
import { Plus_Jakarta_Sans } from 'next/font/google';

import { AppShell } from '@/components/layout/AppShell';
import { LocaleProvider } from '@/lib/i18n';
import { APP_NAME, APP_TAGLINE_FR } from '@/lib/config';

import './globals.css';

const body = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
  weight: ['400', '500', '600', '700'],
});

export const metadata: Metadata = {
  title: {
    default: `${APP_NAME} — Découvrez le Cameroun avec l'IA`,
    template: `%s · ${APP_NAME}`,
  },
  description: APP_TAGLINE_FR,
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    title: `${APP_NAME} — Découvrez le Cameroun avec l'IA`,
    description: 'Explorez les régions, planifiez un voyage et parlez à l’assistant SmartMboa.',
    type: 'website',
    locale: 'fr_CM',
  },
  icons: {
    icon: '/favicon.png',
    apple: '/brand/mark.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body className={`${body.variable} antialiased`}>
        <LocaleProvider>
          <AppShell>{children}</AppShell>
        </LocaleProvider>
      </body>
    </html>
  );
}
