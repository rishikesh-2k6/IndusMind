-- ===========================================================================
-- Industrial Knowledge Brain — Supabase Postgres schema
-- Run in the Supabase SQL editor (or psql). The backend can also auto-create
-- these tables in development via AUTO_CREATE_TABLES=true.
-- ===========================================================================

create extension if not exists "pgcrypto";
create extension if not exists vector;

-- --------------------------------------------------------------------------
-- profiles: role source of truth, keyed by the Supabase auth user id.
-- --------------------------------------------------------------------------
create table if not exists public.profiles (
    id    uuid primary key references auth.users (id) on delete cascade,
    email text not null default '',
    role  text not null default 'user' check (role in ('admin', 'user'))
);

-- Auto-create a profile row whenever a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
    insert into public.profiles (id, email, role)
    values (
        new.id,
        coalesce(new.email, ''),
        coalesce(new.raw_app_meta_data ->> 'role', 'user')
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- --------------------------------------------------------------------------
-- documents
-- --------------------------------------------------------------------------
create table if not exists public.documents (
    id           uuid primary key default gen_random_uuid(),
    file_name    text not null,
    file_type    text not null,
    storage_path text not null default '',
    page_count   integer not null default 0,
    status       text not null default 'processing'
                 check (status in ('processing', 'ready', 'failed')),
    error        text,
    uploaded_by  uuid,
    upload_date  timestamptz not null default now()
);
create index if not exists idx_documents_status on public.documents (status);
create index if not exists idx_documents_upload_date on public.documents (upload_date desc);

-- --------------------------------------------------------------------------
-- chunks
-- --------------------------------------------------------------------------
create table if not exists public.chunks (
    id          uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents (id) on delete cascade,
    chunk_index integer not null,
    text        text not null,
    embedding   vector(768)   -- Gemini text-embedding-004
);
create index if not exists idx_chunks_document on public.chunks (document_id);

-- Approximate-nearest-neighbour index for cosine similarity search.
-- (Build after some rows exist; lists ~ sqrt(rowcount).)
create index if not exists idx_chunks_embedding
    on public.chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- --------------------------------------------------------------------------
-- knowledge graph: entities + relations (equipment history, failure patterns)
-- --------------------------------------------------------------------------
create table if not exists public.kg_entities (
    id          uuid primary key default gen_random_uuid(),
    kind        text not null,   -- equipment | failure | maintenance | inspection | …
    key         text not null,   -- normalized id, e.g. 'p101', 'bearing_wear'
    label       text not null,
    attributes  jsonb,
    document_id uuid references public.documents (id) on delete cascade,
    created_at  timestamptz not null default now()
);
create index if not exists idx_kg_entities_kind_key on public.kg_entities (kind, key);

create table if not exists public.kg_relations (
    id          uuid primary key default gen_random_uuid(),
    src_kind    text not null,
    src_key     text not null,
    dst_kind    text not null,
    dst_key     text not null,
    relation    text not null,   -- has_failure | underwent_maintenance | inspected_in | …
    attributes  jsonb,
    document_id uuid references public.documents (id) on delete cascade,
    created_at  timestamptz not null default now()
);
create index if not exists idx_kg_relations_src on public.kg_relations (src_kind, src_key);
create index if not exists idx_kg_relations_relation on public.kg_relations (relation);

-- --------------------------------------------------------------------------
-- chat_sessions / chat_messages
-- --------------------------------------------------------------------------
create table if not exists public.chat_sessions (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null,
    title      text,
    created_at timestamptz not null default now()
);
create index if not exists idx_chat_sessions_user on public.chat_sessions (user_id);

create table if not exists public.chat_messages (
    id         uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.chat_sessions (id) on delete cascade,
    role       text not null check (role in ('user', 'assistant')),
    content    text not null,
    sources    jsonb,
    created_at timestamptz not null default now()
);
create index if not exists idx_chat_messages_session on public.chat_messages (session_id);

-- --------------------------------------------------------------------------
-- Seed an admin (optional): after creating an auth user, promote them.
--   update public.profiles set role = 'admin' where email = 'you@example.com';
-- --------------------------------------------------------------------------
