'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Compass,
  Home,
  Menu,
  Plane,
  Sparkles,
} from 'lucide-react';

const ITEMS: {
  href: string;
  label: string;
  icon: typeof Home;
  exact?: boolean;
  center?: boolean;
}[] = [
  { href: '/', label: 'Accueil', icon: Home, exact: true },
  { href: '/explorer', label: 'Explorer', icon: Compass },
  { href: '/assistant', label: 'AI', icon: Sparkles, center: true },
  { href: '/mon-voyage', label: 'Voyage', icon: Plane },
  { href: '/planifier', label: 'Menu', icon: Menu },
];

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 border-t border-[var(--line)] bg-[var(--ivory)]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
      aria-label="Navigation mobile"
    >
      <ul className="mx-auto flex h-[4.5rem] max-w-lg items-end justify-around px-2">
        {ITEMS.map((item) => {
          const active = item.exact
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          if (item.center) {
            return (
              <li key={item.href} className="-mt-5">
                <Link
                  href={item.href}
                  className="flex flex-col items-center gap-1"
                  aria-label="Assistant IA"
                >
                  <span
                    className={`flex h-14 w-14 items-center justify-center rounded-full shadow-lg ring-4 ring-[var(--ivory)] transition ${
                      active
                        ? 'bg-[var(--gold)] text-[var(--green-deep)]'
                        : 'bg-[var(--green-deep)] text-white'
                    }`}
                  >
                    <Icon className="h-6 w-6" aria-hidden />
                  </span>
                  <span className="text-[10px] font-semibold text-[var(--green-deep)]">
                    {item.label}
                  </span>
                </Link>
              </li>
            );
          }
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`flex flex-col items-center gap-1 px-2 py-2 text-[10px] font-medium ${
                  active ? 'text-[var(--green-deep)]' : 'text-[var(--muted)]'
                }`}
                aria-current={active ? 'page' : undefined}
              >
                <Icon
                  className={`h-5 w-5 ${active ? 'text-[var(--gold)]' : ''}`}
                  aria-hidden
                />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
