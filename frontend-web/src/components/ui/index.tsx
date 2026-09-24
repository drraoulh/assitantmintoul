import Link from 'next/link';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'gold';
type Size = 'sm' | 'md' | 'lg';

const variants: Record<Variant, string> = {
  primary:
    'bg-[var(--green-deep)] text-white hover:bg-[var(--green)] shadow-sm',
  secondary:
    'bg-[var(--mint-soft)] text-[var(--green-deep)] hover:bg-[var(--line)]',
  ghost:
    'bg-transparent text-white border border-white/30 hover:bg-white/10',
  outline:
    'bg-transparent text-[var(--green-deep)] border border-[var(--line)] hover:border-[var(--gold)] hover:bg-[var(--mint-soft)]',
  gold:
    'bg-[var(--gold)] text-[var(--green-deep)] hover:brightness-105 shadow-sm',
  danger: 'bg-[var(--danger)] text-white hover:brightness-110',
};

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'px-6 py-3.5 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  href,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  href?: string;
  children: ReactNode;
}) {
  const cls = `inline-flex items-center justify-center gap-2 rounded-full font-semibold transition active:scale-[0.97] disabled:opacity-60 ${variants[variant]} ${sizes[size]} ${className}`;
  if (href) {
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  }
  return (
    <button className={cls} {...props}>
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = 'green',
}: {
  children: ReactNode;
  tone?: 'green' | 'gold' | 'muted' | 'danger';
}) {
  const tones = {
    green: 'bg-[var(--mint-soft)] text-[var(--green-deep)]',
    gold: 'bg-[var(--gold)]/25 text-[var(--green-deep)]',
    muted: 'bg-[var(--line)] text-[var(--muted)]',
    danger: 'bg-[var(--danger)]/10 text-[var(--danger)]',
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`skeleton-shimmer rounded-xl ${className}`}
      aria-hidden
    />
  );
}

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body?: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--line)] bg-white/60 px-6 py-10 text-center">
      <p className="font-display text-lg font-semibold text-[var(--green-deep)]">
        {title}
      </p>
      {body ? <p className="mt-2 text-sm text-[var(--muted)]">{body}</p> : null}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div
      className="rounded-2xl border border-[var(--danger)]/20 bg-[var(--danger)]/5 px-5 py-4 text-sm text-[var(--danger)]"
      role="alert"
    >
      <p className="font-semibold">SmartMboa rencontre momentanément un problème.</p>
      <p className="mt-1 opacity-90">{message}</p>
      <p className="mt-2 text-[var(--muted)]">Réessayez dans quelques instants.</p>
    </div>
  );
}

export function Input({
  className = '',
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none transition placeholder:text-[var(--muted)] focus:border-[var(--gold)] focus:ring-2 focus:ring-[var(--gold)]/30 ${className}`}
      {...props}
    />
  );
}

export function Select({
  className = '',
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none focus:border-[var(--gold)] focus:ring-2 focus:ring-[var(--gold)]/30 ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

export function TextArea({
  className = '',
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`w-full rounded-2xl border border-[var(--line)] bg-white px-4 py-3 text-[var(--ink)] outline-none focus:border-[var(--gold)] focus:ring-2 focus:ring-[var(--gold)]/30 ${className}`}
      {...props}
    />
  );
}

export function ThinkingDots({ label = 'SmartMboa réfléchit…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-[var(--muted)]" aria-live="polite">
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--green)]"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </span>
      {label}
    </div>
  );
}
