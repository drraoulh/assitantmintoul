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
  const isGroupRoom = /^\/groupe\/[^/]+$/.test(pathname);
  const isFullHeight = isAssistant || isGroupRoom;

  return (
    <div
      className={
        isFullHeight
          ? 'flex h-[100dvh] min-h-[100dvh] flex-col overflow-hidden'
          : 'flex min-h-[100svh] flex-col'
      }
    >
      <ScrollToTop />
      <SiteHeader />
      <main
        className={
          isFullHeight
            ? 'flex min-h-0 flex-1 flex-col overflow-hidden'
            : 'flex-1 pb-bottom-nav'
        }
      >
        {children}
      </main>
      {isFullHeight ? null : <SiteFooter />}
      {isFullHeight ? null : <MobileBottomNav />}
    </div>
  );
}
