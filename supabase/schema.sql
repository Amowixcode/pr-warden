-- pr-warden Supabase schema: review/ingest history storage.
-- Additive to the local JSON caches (./data/review_history.json, ./data/ingest_history.json)
-- used for incremental review/ingest — this schema only backs GET /reviews and reporting.
--
-- Run this in the Supabase SQL editor (or `psql`/`supabase db push`) once per project.

create table if not exists reviews (
    id bigint generated always as identity primary key,
    repo text not null,
    pr_number integer not null,
    head_sha text not null,
    verdict text not null,
    summary text not null,
    issues jsonb not null default '[]'::jsonb,
    suggestions jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists reviews_repo_pr_number_idx on reviews (repo, pr_number);
create index if not exists reviews_created_at_idx on reviews (created_at desc);

create table if not exists ingests (
    id bigint generated always as identity primary key,
    repo text not null,
    last_ingested_at timestamptz not null,
    issues_count integer not null default 0,
    merged_prs_count integer not null default 0,
    commits_count integer not null default 0
);

create index if not exists ingests_repo_idx on ingests (repo);
