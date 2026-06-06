-- =====================================================
-- ClientMetrics — Schema do Supabase
-- Rodar 1x no SQL Editor do Supabase
-- https://supabase.com/dashboard/project/gipuopmdksagqkuuastc/sql
-- =====================================================

-- Extensões úteis
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabela de usuários (Patricia admin + cada cliente)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'client')),
    name TEXT NOT NULL,
    client_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de clientes (multi-tenant)
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    logo TEXT,
    color TEXT,
    paid_traffic BOOLEAN DEFAULT false,
    notes TEXT,
    checklist_data JSONB,
    logo_path TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de métricas (pra futuro — coleta de dados reais)
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    source TEXT NOT NULL,
    leads INT DEFAULT 0,
    clicks INT DEFAULT 0,
    spend NUMERIC(10,2) DEFAULT 0,
    impressions INT DEFAULT 0,
    reach INT DEFAULT 0,
    followers INT DEFAULT 0,
    reviews_count INT DEFAULT 0,
    reviews_avg NUMERIC(2,1),
    extra_data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- PROSPECÇÃO — Cold outreach + CRM
-- Adicionado em 06/06/2026
-- =====================================================

-- Tabela de leads (cold list de telefones)
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone TEXT NOT NULL,
    name TEXT,
    email TEXT,
    address TEXT,
    city TEXT,
    website TEXT,
    instagram TEXT,
    facebook TEXT,
    google_business_url TEXT,
    source TEXT,  -- 'cold_call', 'indicacao', 'site_form', 'manual', 'csv_upload'
    status TEXT NOT NULL DEFAULT 'novo' CHECK (status IN (
        'novo', 'em_contato', 'coletando', 'analisado', 'proposta', 'ganho', 'perdido'
    )),
    notes TEXT,
    tags TEXT[],
    estimated_value NUMERIC(10,2),
    last_contact_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Log de atividades do lead
CREATE TABLE IF NOT EXISTS lead_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    type TEXT NOT NULL,  -- 'message_sent', 'reply', 'info_added', 'status_change', 'proposal_sent', 'note'
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Templates de mensagem (cold, follow-up, proposta)
CREATE TABLE IF NOT EXISTS message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'sms', 'email')),
    category TEXT,  -- 'cold_outreach', 'follow_up', 'proposal', 'info_request', etc
    body TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Análises automáticas (quando lead entra em "analisado")
CREATE TABLE IF NOT EXISTS lead_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    website_score INT,  -- 0-100
    ig_exists BOOLEAN,
    ig_followers INT,
    fb_exists BOOLEAN,
    gbp_exists BOOLEAN,
    gbp_rating NUMERIC(2,1),
    gbp_reviews_count INT,
    opportunities JSONB,  -- [{type: 'no_gbp', priority: 'high', description: '...'}, ...]
    services_recommended TEXT[],
    summary TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- CHECKLIST DE MELHORIAS POR CLIENTE (06/06/2026)
-- Patricia vê e marca no admin
-- =====================================================

CREATE TABLE IF NOT EXISTS client_checklist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    category TEXT NOT NULL,  -- 'instagram', 'facebook', 'gbp', 'site', 'meta_ads', 'google_ads', 'reviews', 'custom'
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done', 'blocked')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    assigned_to TEXT,  -- 'patricia', 'claude', 'client'
    due_date DATE,
    completed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Integrações por cliente (status de cada plataforma conectada)
CREATE TABLE IF NOT EXISTS client_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,  -- 'meta_ads', 'google_ads', 'gbp', 'instagram', 'facebook', 'ga4', 'site'
    status TEXT DEFAULT 'disconnected' CHECK (status IN ('disconnected', 'pending_auth', 'connected', 'error')),
    access_token TEXT,  -- em produção: encriptar
    refresh_token TEXT,
    account_id TEXT,  -- ad account ID, page ID, location ID, etc
    account_name TEXT,  -- nome human-readable
    last_sync_at TIMESTAMPTZ,
    last_error TEXT,
    connected_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, platform)
);

-- Métricas diárias expandidas (mais flexível que a tabela metrics genérica)
CREATE TABLE IF NOT EXISTS client_metrics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    source TEXT NOT NULL,  -- 'meta_ads', 'google_ads', 'gbp', 'instagram', 'facebook', 'ga4', 'site'
    metric_name TEXT NOT NULL,  -- 'leads', 'clicks', 'spend', 'impressions', 'reach', 'followers', 'reviews', 'views', 'calls', etc
    metric_value NUMERIC,
    extra_data JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, date, source, metric_name)
);

-- =====================================================
-- Índices
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_metrics_client_id ON metrics(client_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(date);
CREATE INDEX IF NOT EXISTS idx_metrics_source ON metrics(source);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_client_id ON users(client_id);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_activities_lead_id ON lead_activities(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_analyses_lead_id ON lead_analyses(lead_id);

CREATE INDEX IF NOT EXISTS idx_client_checklist_client_id ON client_checklist_items(client_id);
CREATE INDEX IF NOT EXISTS idx_client_checklist_status ON client_checklist_items(status);
CREATE INDEX IF NOT EXISTS idx_client_integrations_client_id ON client_integrations(client_id);
CREATE INDEX IF NOT EXISTS idx_client_integrations_platform ON client_integrations(platform);
CREATE INDEX IF NOT EXISTS idx_client_metrics_daily_client_date ON client_metrics_daily(client_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_client_metrics_daily_source ON client_metrics_daily(source);

-- =====================================================
-- Templates iniciais (cold outreach padrão)
-- =====================================================

INSERT INTO message_templates (name, channel, category, body) VALUES
('Cold outreach inicial (WhatsApp)', 'whatsapp', 'cold_outreach',
 'Oi, {{nome}}! Tudo bem?\n\nSou a Patricia, trabalho com marketing digital e ajudo negócios como o seu a aparecer mais no Google e Instagram.\n\nPosso fazer uma análise gratuita de como sua empresa aparece online? Se tiver, me passa seu Instagram e site que em 48h te mando um relatório personalizado com 3 pontos pra melhorar.\n\nSem compromisso! Vale?'),
('Follow-up 1 (3 dias depois)', 'whatsapp', 'follow_up',
 'Oi, {{nome}}! Sou eu, Patricia, do marketing.\n\nMandei mensagem dia {{data_envio}} oferecendo uma análise gratuita. Conseguiu ver?\n\nSe quiser, me responde com seu Instagram ou site que eu mando o relatório. 🙂'),
('Coleta de info', 'whatsapp', 'info_request',
 'Oi, {{nome}}! Pra eu fechar a análise, me passa:\n\n1. Instagram (se tiver)\n2. Site (se tiver)\n3. Link do Google Maps do seu negócio\n\nValeu!'),
('Envio da análise + proposta', 'whatsapp', 'proposal',
 'Oi, {{nome}}! Aqui tá o relatório que prometi: [link]\n\n3 pontos que vi de oportunidade pra você:\n1. {{oportunidade_1}}\n2. {{oportunidade_2}}\n3. {{oportunidade_3}}\n\nQuer agendar 15min pra eu te mostrar como resolver?\n\nPatricia')
ON CONFLICT DO NOTHING;

-- NOTA: dados iniciais (4 users + 3 clients) são inseridos via migrate_to_supabase.py
-- depois das tabelas existirem.
