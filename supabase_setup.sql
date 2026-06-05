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

-- Índices
CREATE INDEX IF NOT EXISTS idx_metrics_client_id ON metrics(client_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(date);
CREATE INDEX IF NOT EXISTS idx_metrics_source ON metrics(source);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_client_id ON users(client_id);

-- NOTA: dados iniciais (4 users + 3 clients) são inseridos via migrate_to_supabase.py
-- depois das tabelas existirem.
