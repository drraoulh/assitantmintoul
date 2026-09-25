'use client';

import { usePathname } from 'next/navigation';

import { MobileBottomNav } from '@/components/layout/MobileBottomNav';
import { SiteFooter, SiteHeader } from '@/components/layout/SiteHeader';
import { ScrollToTop } from '@/components/layout/ScrollToTop';

/**
 * App chrome — hide site footer + bottom nav on /assistant (full-height chat).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAssistant = pathname === '/assistant' || pathname.startsWith('/assistant/');

  return (
    <div
      className={
        isAssistant
          ? 'flex h-[100dvh] min-h-[100dvh] flex-col overflow-hidden'
          : 'flex min-h-[100svh] flex-col'
      }
    >
      <ScrollToTop />
      <SiteHeader />
      <main
        className={
          isAssistant
            ? 'flex min-h-0 flex-1 flex-col overflow-hidden'
            : 'flex-1 pb-bottom-nav'
        }
      >
        {children}
      </main>
      {isAssistant ? null : <SiteFooter />}
      {isAssistant ? null : <MobileBottomNav />}
    </div>
  );
}
