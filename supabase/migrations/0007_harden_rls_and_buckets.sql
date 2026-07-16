-- Defense-in-depth hardening for the metering tables and storage buckets.

-- 1. FORCE row level security on the metering tables. They already have RLS
--    enabled with owner-only SELECT policies, but without FORCE the table owner
--    role bypasses those policies. FORCE closes that gap. (The backend uses the
--    service role, which still bypasses RLS by design.)
alter table public.app_users force row level security;
alter table public.user_daily_usage force row level security;

-- 2. Create the storage buckets as PRIVATE from the migration instead of
--    relying on someone remembering to do it (and to keep them non-public).
--    Wrapped in a guard so this migration still runs where the storage schema
--    is unavailable (e.g. a plain Postgres used in CI).
do $$
begin
  if exists (
    select 1 from pg_namespace where nspname = 'storage'
  ) and exists (
    select 1 from pg_class
    where relname = 'buckets'
      and relnamespace = (select oid from pg_namespace where nspname = 'storage')
  ) then
    insert into storage.buckets (id, name, public)
      values ('documents', 'documents', false)
      on conflict (id) do update set public = false;
    insert into storage.buckets (id, name, public)
      values ('exports', 'exports', false)
      on conflict (id) do update set public = false;
  end if;
end $$;
