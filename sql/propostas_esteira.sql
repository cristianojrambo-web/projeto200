-- Esteira de Propostas — tabela isolada, sem relação com leads/clientes/atividades/pipeline_stages.
-- Rode isso uma vez no SQL Editor do Supabase (projeto do CRM Seguros).

create table public.propostas_esteira (
  id               uuid primary key default gen_random_uuid(),
  numero_proposta  text,
  segurado         text,
  tipo             text,
  status           text not null default 'para_lancar'
                     check (status in ('aguardando_data','para_lancar','lancada_auto','lancada_manual','concluida')),
  data_lancamento  date,
  motivo_manual    text,
  observacoes      text,
  arquivo_nome     text unique,
  arquivo_caminho  text,
  registrado_por   uuid references auth.users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

-- numero_proposta/segurado ficam em branco quando o card nasce sozinho a partir de um PDF
-- detectado na pasta de rede (arquivo_nome preenchido) — a secretária completa na tela.
-- Cadastro manual (sem arquivo) continua exigindo os dois campos, controlado pela aplicação.

alter table public.propostas_esteira enable row level security;

-- Só gestor e secretária podem ver/editar — reforça no banco o que a aba já esconde na tela.
-- Requer que a role de cada usuário esteja em public.profiles.role (mesma tabela que o CRM já usa).
create policy "gestor e secretaria acessam a esteira"
  on public.propostas_esteira
  for all
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role in ('gestor','secretaria')
    )
  )
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role in ('gestor','secretaria')
    )
  );
