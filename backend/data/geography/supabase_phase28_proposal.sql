-- Phase 2.8 — proposed Supabase geography enrichment (NOT auto-applied).
-- Inspect live schema first. Prefer additive columns / tables.
-- Do not delete existing places / regions / cities data.

-- Optional: departments (divisions)
-- create table if not exists public.divisions (
--   id uuid primary key default gen_random_uuid(),
--   slug text unique not null,
--   name_fr text not null,
--   name_en text,
--   region_id uuid references public.regions(id),
--   source_id uuid,
--   verified_at date,
--   created_at timestamptz default now()
-- );

-- Optional additive columns on cities:
-- alter table public.cities add column if not exists division_id uuid references public.divisions(id);
-- alter table public.cities add column if not exists is_region_capital boolean default false;
-- alter table public.cities add column if not exists is_national_capital boolean default false;

-- Optional additive columns on places:
-- alter table public.places add column if not exists locality text;
-- alter table public.places add column if not exists location_scope text;
--   -- IN_CITY | NEARBY | IN_REGION

-- Seed references live in backend/data/geography/cameroon_admin.json
-- until a controlled Supabase migration is approved.
