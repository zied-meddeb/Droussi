-- Atomic daily-usage increment.
--
-- The application previously did a read-modify-write (SELECT the row, then
-- UPDATE with count+1) to bump exam_count / cost_usd. Two concurrent exam
-- generations could both read the same starting value and each write back
-- +1, losing one increment (a user could exceed the daily quota, or spend
-- could be under-counted for the global circuit breaker). This function folds
-- the whole operation into a single upsert so Postgres serializes it on the
-- (user_id, usage_date) unique constraint.

create or replace function public.increment_daily_usage(
  p_user_id uuid,
  p_exams integer,
  p_cost numeric
) returns integer
language sql
security definer
set search_path = public
as $$
  insert into public.user_daily_usage (user_id, usage_date, exam_count, cost_usd)
  values (
    p_user_id,
    (timezone('utc', now()))::date,
    greatest(p_exams, 0),
    greatest(p_cost, 0)
  )
  on conflict (user_id, usage_date) do update
    set exam_count = public.user_daily_usage.exam_count + greatest(p_exams, 0),
        cost_usd = public.user_daily_usage.cost_usd + greatest(p_cost, 0),
        updated_at = now()
  returning exam_count;
$$;

-- Only the backend (service role) calls this; do not expose it to anon/auth.
revoke all on function public.increment_daily_usage(uuid, integer, numeric) from public;
revoke all on function public.increment_daily_usage(uuid, integer, numeric) from anon;
revoke all on function public.increment_daily_usage(uuid, integer, numeric) from authenticated;
