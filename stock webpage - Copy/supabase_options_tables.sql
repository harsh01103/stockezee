create table if not exists option_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  underlying_symbol text not null,
  expiry date not null,
  spot_price numeric(14,4) not null,
  atm_strike numeric(14,4) not null,
  market_status text not null,
  generated_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb
);

create index if not exists option_snapshots_lookup_idx
  on option_snapshots (underlying_symbol, expiry, generated_at desc);

create table if not exists option_chain (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid references option_snapshots(id) on delete cascade,
  user_id uuid,
  underlying_symbol text not null,
  expiry date not null,
  strike numeric(14,4) not null,
  call_payload jsonb not null default '{}'::jsonb,
  put_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists option_chain_lookup_idx
  on option_chain (underlying_symbol, expiry, strike);

create table if not exists watchlist (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  contract_symbol text not null,
  underlying text not null,
  expiry date not null,
  strike numeric(14,4) not null,
  side text not null,
  pinned boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists watchlist_user_idx
  on watchlist (user_id, created_at desc);

create table if not exists paper_positions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  underlying text not null,
  expiry date not null,
  strike numeric(14,4) not null,
  side text not null,
  action text not null,
  entry numeric(14,4) not null,
  exit numeric(14,4),
  pnl numeric(14,4),
  notes text not null default '',
  created_at timestamptz not null default now()
);

create index if not exists paper_positions_user_idx
  on paper_positions (user_id, created_at desc);

create table if not exists analytics_cache (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  underlying_symbol text not null,
  expiry date not null,
  analytics jsonb not null default '{}'::jsonb,
  generated_at timestamptz not null default now()
);

create index if not exists analytics_cache_lookup_idx
  on analytics_cache (underlying_symbol, expiry, generated_at desc);
