-- =====================================================
-- ClientMetrics — Schema do Supabase
-- Rodar 1x no SQL Editor do Supabase
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
    client_id TEXT,  -- NULL pra admin, referencia clients.id pra clientes
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de clientes (multi-tenant)
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,  -- ex: 'benalex', 'econoclub', 'dyemys'
    name TEXT NOT NULL,
    logo TEXT,  -- emoji ou path
    color TEXT,  -- hex
    paid_traffic BOOLEAN DEFAULT false,
    notes TEXT,
    checklist_data JSONB,  -- { total: 41, done: 6, in_progress: 0, file: '...' }
    logo_path TEXT,  -- caminho pra imagem do logo
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tabela de métricas (pra futuro — coleta de dados reais)
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    source TEXT NOT NULL,  -- 'meta_ads', 'google_ads', 'ga4', 'gbp', 'ig', 'manual'
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

-- Índices pra performance
CREATE INDEX IF NOT EXISTS idx_metrics_client_id ON metrics(client_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(date);
CREATE INDEX IF NOT EXISTS idx_metrics_source ON metrics(source);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_client_id ON users(client_id);

-- =====================================================
-- Dados iniciais
-- (Patricia admin + 3 clientes: EconoClub, Benalex, DYEMY'S)
-- =====================================================

-- Os hashes de senha abaixo correspondem a 'admin123' (Patricia) e 'cliente123' (clientes)
-- Gerados com werkzeug.security.generate_password_hash('admin123') etc.

INSERT INTO users (email, password_hash, role, name, client_id) VALUES
    ('patricia@agencia.com', 'GENERATED_AT_MIGRATION', 'admin', 'Patricia', NULL),
    ('econoclub@cliente.com', 'GENERATED_AT_MIGRATION', 'client', 'EconoClub', 'econoclub'),
    ('benalex@cliente.com', 'GENERATED_AT_MIGRATION', 'client', 'Benalex Cleaning', 'benalex'),
    ('dyemys@cliente.com', 'GENERATED_AT_MIGRATION', 'client', "DYEMY'S Painting", 'dyemys')
ON CONFLICT (email) DO NOTHING;

INSERT INTO clients (id, name, logo, color, paid_traffic, notes, checklist_data, logo_path) VALUES
    ('econoclub', 'EconoClub', '🌱', '#10b981', false,
     'Cliente-piloto da Fase 1. Migração Square → Stripe em andamento.',
     '{"total": 32, "done": 0, "in_progress": 0, "file": "CLIENTES/ECONOCLUB/CHECKLIST.md"}'::jsonb,
     NULL),
    ('benalex', 'Benalex Cleaning Services', '🧹', '#0099ff', false,
     'GBP FINALIZADO 04/06. Endereço escondido (service area). 5 fotos enviadas. Pronto pra entregar.',
     '{"total": 41, "done": 6, "in_progress": 0, "file": "CLIENTES/BENALEX/CHECKLIST.md"}'::jsonb,
     '../BENALEX/logo.png'),
    ('dyemys', 'DYEMY''S Painting', '🎨', '#1a2e4a', false,
     'GBP FINALIZADO 04/06. Sem endereço. 5 fotos enviadas. Pronto pra entregar.',
     '{"total": 41, "done": 6, "in_progress": 0, "file": "CLIENTES/DYEMYS/CHECKLIST.md"}'::jsonb,
     '../DYEMYS/logo.jpg')
ON CONFLICT (id) DO NOTHING;
