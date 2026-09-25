'use client';

import {
  useDeferredValue,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { Loader2, MapPin } from 'lucide-react';

import { Input } from '@/components/ui';
import {
  resolveCameroonDestination,
  suggestCameroonDestinations,
  type CameroonDestination,
} from '@/lib/cameroon-destinations';

const NOT_FOUND_MSG = 'Area not found in Cameroon, check spelling';

type Props = {
  value: string;
  onChange: (value: string) => void;
  onValidityChange?: (valid: boolean) => void;
  placeholder?: string;
  required?: boolean;
  locale?: 'fr' | 'en';
};

export function DestinationAutocomplete({
  value,
  onChange,
  onValidityChange,
  placeholder = 'Ex. Bafoussam, Limbé, Yaoundé…',
  required,
  locale = 'fr',
}: Props) {
  const listId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [touched, setTouched] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const deferred = useDeferredValue(value.trim());

  const suggestions = useMemo(
    () => suggestCameroonDestinations(deferred, 8),
    [deferred],
  );

  const resolved = useMemo(
    () => (deferred.length >= 2 ? resolveCameroonDestination(deferred) : null),
    [deferred],
  );

  const showError =
    touched &&
    deferred.length >= 2 &&
    !resolved &&
    suggestions.length === 0;

  const valid = deferred.length === 0 ? !required : !!resolved;

  useEffect(() => {
    onValidityChange?.(valid);
  }, [valid, onValidityChange]);

  // Light “analyzer” pulse while the deferred query catches up
  useEffect(() => {
    if (!value.trim()) {
      setAnalyzing(false);
      return;
    }
    if (value.trim() !== deferred) {
      setAnalyzing(true);
      return;
    }
    const t = window.setTimeout(() => setAnalyzing(false), 180);
    return () => clearTimeout(t);
  }, [value, deferred]);

  useEffect(() => {
    setActiveIndex(0);
  }, [deferred]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  function pick(dest: CameroonDestination) {
    onChange(dest.name);
    setOpen(false);
    setTouched(true);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true);
      return;
    }
    if (!open || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter' && open) {
      e.preventDefault();
      const dest = suggestions[activeIndex];
      if (dest) pick(dest);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  const statusLabel = analyzing
    ? locale === 'en'
      ? 'Checking destination…'
      : 'Vérification de la destination…'
    : resolved
      ? locale === 'en'
        ? `Matched: ${resolved.name}${resolved.region ? ` · ${resolved.region}` : ''}`
        : `Reconnu : ${resolved.name}${resolved.region ? ` · ${resolved.region}` : ''}`
      : null;

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <MapPin
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]"
          aria-hidden
        />
        <Input
          className={`pl-9 pr-10 ${
            showError
              ? 'border-[var(--danger)] focus:border-[var(--danger)] focus:ring-[var(--danger)]/30'
              : resolved
                ? 'border-[var(--green)] focus:border-[var(--green)]'
                : ''
          }`}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
            setTouched(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTouched(true)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          required={required}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-invalid={showError}
          autoComplete="off"
        />
        {analyzing ? (
          <Loader2
            className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-[var(--green)]"
            aria-hidden
          />
        ) : null}
      </div>

      {statusLabel && !showError ? (
        <p className="mt-1.5 text-xs text-[var(--green)]" aria-live="polite">
          {statusLabel}
        </p>
      ) : null}

      {showError ? (
        <p className="mt-1.5 text-sm text-[var(--danger)]" role="alert">
          {NOT_FOUND_MSG}
        </p>
      ) : null}

      {open && suggestions.length > 0 ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-56 w-full overflow-auto rounded-2xl border border-[var(--line)] bg-white py-1 shadow-[var(--shadow-lift)]"
        >
          {suggestions.map((dest, i) => (
            <li key={dest.id} role="option" aria-selected={i === activeIndex}>
              <button
                type="button"
                className={`flex w-full items-start gap-2 px-3 py-2.5 text-left text-sm transition ${
                  i === activeIndex
                    ? 'bg-[var(--mint-soft)] text-[var(--green-deep)]'
                    : 'text-[var(--ink)] hover:bg-[var(--mint-soft)]/70'
                }`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(dest)}
              >
                <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--gold)]" aria-hidden />
                <span>
                  <span className="font-semibold">{dest.name}</span>
                  {dest.region ? (
                    <span className="mt-0.5 block text-xs text-[var(--muted)]">
                      {dest.region}
                      {dest.kind === 'region'
                        ? locale === 'en'
                          ? ' · region'
                          : ' · région'
                        : dest.kind === 'place'
                          ? locale === 'en'
                            ? ' · place'
                            : ' · site'
                          : ''}
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
