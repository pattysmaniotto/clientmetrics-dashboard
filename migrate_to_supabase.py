"""
migrate_to_supabase.py
Migra dados mock do app.py pro Supabase + gera hashes de senha corretos.

Uso: python migrate_to_supabase.py
Requer: DATABASE_URL como env var (formato postgresql://user:pass@host:port/db)
"""

import os
import sys
from werkzeug.security import generate_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_url():
    """Pega a URL do banco. Em prod, vem do env var. Em dev, do .env."""
    url = os.environ.get('DATABASE_URL')
    if not url:
        # Tenta ler do .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            url = os.environ.get('DATABASE_URL')
        except ImportError:
            pass
    if not url:
        print('ERRO: DATABASE_URL não definida.')
        print('Configure no .env ou como variável de ambiente:')
        print('  export DATABASE_URL="postgresql://postgres:senha@db.xxx.supabase.co:5432/postgres"')
        sys.exit(1)
    return url


def run_schema(conn):
    """Cria as tabelas se não existirem."""
    schema_path = os.path.join(os.path.dirname(__file__), 'supabase_schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print('✓ Schema criado/atualizado (tabelas users, clients, metrics)')


def insert_initial_data(conn):
    """Insere/atualiza os 4 usuários e 3 clientes iniciais."""
    users = [
        ('patricia@agencia.com', 'admin123', 'admin', 'Patricia', None),
        ('econoclub@cliente.com', 'cliente123', 'client', 'EconoClub', 'econoclub'),
        ('benalex@cliente.com', 'cliente123', 'client', 'Benalex Cleaning', 'benalex'),
        ('dyemys@cliente.com', 'cliente123', 'client', "DYEMY'S Painting", 'dyemys'),
    ]

    with conn.cursor() as cur:
        for email, password, role, name, client_id in users:
            password_hash = generate_password_hash(password)
            cur.execute("""
                INSERT INTO users (email, password_hash, role, name, client_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    name = EXCLUDED.name,
                    client_id = EXCLUDED.client_id
            """, (email, password_hash, role, name, client_id))
            print(f'  ✓ Usuário: {email}')

        clients = [
            ('econoclub', 'EconoClub', '🌱', '#10b981', False,
             'Cliente-piloto da Fase 1. Migração Square → Stripe em andamento.',
             '{"total": 32, "done": 0, "in_progress": 0}', None),
            ('benalex', 'Benalex Cleaning Services', '🧹', '#0099ff', False,
             'GBP FINALIZADO 04/06. Endereço escondido (service area). 5 fotos enviadas. Pronto pra entregar.',
             '{"total": 41, "done": 6, "in_progress": 0}', '../BENALEX/logo.png'),
            ('dyemys', "DYEMY'S Painting", '🎨', '#1a2e4a', False,
             'GBP FINALIZADO 04/06. Sem endereço. 5 fotos enviadas. Pronto pra entregar.',
             '{"total": 41, "done": 6, "in_progress": 0}', '../DYEMYS/logo.jpg'),
        ]

        for cid, name, logo, color, paid, notes, checklist_json, logo_path in clients:
            cur.execute("""
                INSERT INTO clients (id, name, logo, color, paid_traffic, notes, checklist_data, logo_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    logo = EXCLUDED.logo,
                    color = EXCLUDED.color,
                    paid_traffic = EXCLUDED.paid_traffic,
                    notes = EXCLUDED.notes,
                    checklist_data = EXCLUDED.checklist_data,
                    logo_path = EXCLUDED.logo_path
            """, (cid, name, logo, color, paid, notes, checklist_json, logo_path))
            print(f'  ✓ Cliente: {name}')

    conn.commit()
    print('✓ Dados iniciais inseridos/atualizados')


def verify(conn):
    """Mostra o que ficou no banco."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT email, role, name, client_id FROM users ORDER BY role, email')
        users = cur.fetchall()
        cur.execute('SELECT id, name, logo, color FROM clients ORDER BY id')
        clients = cur.fetchall()

    print()
    print('=' * 60)
    print('VERIFICAÇÃO FINAL:')
    print('=' * 60)
    print(f'\n✓ {len(users)} usuários no banco:')
    for u in users:
        print(f'   - {u["email"]} ({u["role"]}, {u["name"]})')
    print(f'\n✓ {len(clients)} clientes no banco:')
    for c in clients:
        print(f'   - {c["id"]}: {c["name"]} {c["logo"]}')


def main():
    print('=' * 60)
    print('MIGRAÇÃO: Mock → Supabase (Postgres)')
    print('=' * 60)

    db_url = get_db_url()
    print(f'\nConectando ao banco...')

    # Supabase requer SSL
    conn = psycopg2.connect(db_url, sslmode='require')
    print('✓ Conectado!')

    try:
        run_schema(conn)
        insert_initial_data(conn)
        verify(conn)
        print()
        print('=' * 60)
        print('✅ MIGRAÇÃO COMPLETA!')
        print('=' * 60)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
