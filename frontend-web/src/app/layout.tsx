import type { Metadata } from 'next';
import { Plus_Jakarta_Sans } from 'next/font/google';

import { MobileBottomNav } from '@/components/layout/MobileBottomNav';
import { SiteFooter, SiteHeader } from '@/components/layout/SiteHeader';
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
  openGraph: {
    title: `${APP_NAME} — Découvrez le Cameroun avec l'IA`,
    description: 'Explorez les régions, planifiez un voyage et parlez à l’assistant SmartMboa.',
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
      <body className={`${body.variable} antialiased`}>
        <LocaleProvider>
          <div className="flex min-h-[100svh] flex-col">
            <SiteHeader />
            <main className="flex-1 pb-bottom-nav">{children}</main>
            <SiteFooter />
            <MobileBottomNav />
          </div>
        </LocaleProvider>
      </body>
    </html>
  );
}
