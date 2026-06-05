"""
migrate_to_supabase.py
Migra dados mock do app.py pro Supabase via REST API.

Uso: SUPABASE_KEY="..." python migrate_to_supabase.py
"""

import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega .env da mesma pasta do script
load_dotenv(Path(__file__).parent / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://gipuopmdksagqkuuastc.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')


def get_client() -> Client:
    if not SUPABASE_KEY:
        print('ERRO: SUPABASE_KEY nao definida.')
        print('Rode: SUPABASE_KEY="eyJ..." python migrate_to_supabase.py')
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def create_tables_manually(supabase):
    """Cria as tabelas via SQL Editor (precisa rodar 1x no dashboard)."""
    print()
    print('=' * 60)
    print('ATENCAO: ANTES DE RODAR ESSE SCRIPT,')
    print('rode o conteudo de supabase_schema.sql no SQL Editor')
    print('do Supabase (https://supabase.com/dashboard/project/_/sql)')
    print('=' * 60)
    print()
    resp = input('Tabelas ja foram criadas? (s/n): ').strip().lower()
    if resp not in ('s', 'sim', 'y', 'yes'):
        print('Cria as tabelas primeiro e roda de novo.')
        sys.exit(0)


def insert_initial_data(supabase):
    """Insere/atualiza os 4 usuarios e 3 clientes iniciais."""
    users = [
        ('patricia@agencia.com', 'admin123', 'admin', 'Patricia', None),
        ('econoclub@cliente.com', 'cliente123', 'client', 'EconoClub', 'econoclub'),
        ('benalex@cliente.com', 'cliente123', 'client', 'Benalex Cleaning', 'benalex'),
        ('dyemys@cliente.com', 'cliente123', 'client', "DYEMY'S Painting", 'dyemys'),
    ]

    print('Inserindo usuarios...')
    for email, password, role, name, client_id in users:
        password_hash = generate_password_hash(password)
        data = {
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'name': name,
            'client_id': client_id,
        }
        try:
            # Tenta inserir; se ja existe, atualiza
            supabase.table('users').upsert(data).execute()
            print(f'  [OK] Usuario: {email}')
        except Exception as e:
            print(f'  [ERRO] {email}: {e}')

    clients = [
        ('econoclub', 'EconoClub', '🌱', '#10b981', False,
         'Cliente-piloto da Fase 1. Migracao Square -> Stripe em andamento.',
         {'total': 32, 'done': 0, 'in_progress': 0}, None),
        ('benalex', 'Benalex Cleaning Services', '🧹', '#0099ff', False,
         'GBP FINALIZADO 04/06. Endereco escondido (service area). 5 fotos enviadas. Pronto pra entregar.',
         {'total': 41, 'done': 6, 'in_progress': 0}, '../BENALEX/logo.png'),
        ('dyemys', "DYEMY'S Painting", '🎨', '#1a2e4a', False,
         'GBP FINALIZADO 04/06. Sem endereco. 5 fotos enviadas. Pronto pra entregar.',
         {'total': 41, 'done': 6, 'in_progress': 0}, '../DYEMYS/logo.jpg'),
    ]

    print('Inserindo clientes...')
    for cid, name, logo, color, paid, notes, checklist_json, logo_path in clients:
        data = {
            'id': cid,
            'name': name,
            'logo': logo,
            'color': color,
            'paid_traffic': paid,
            'notes': notes,
            'checklist_data': checklist_json,
            'logo_path': logo_path,
        }
        try:
            supabase.table('clients').upsert(data).execute()
            print(f'  [OK] Cliente: {name}')
        except Exception as e:
            print(f'  [ERRO] {name}: {e}')


def verify(supabase):
    """Verifica o que ficou no banco."""
    print()
    print('=' * 60)
    print('VERIFICACAO:')
    print('=' * 60)

    users = supabase.table('users').select('email, role, name, client_id').order('role').execute()
    print(f'\n[OK] {len(users.data)} usuarios:')
    for u in users.data:
        print(f'   - {u["email"]} ({u["role"]}, {u["name"]})')

    clients = supabase.table('clients').select('id, name, logo').order('id').execute()
    print(f'\n[OK] {len(clients.data)} clientes:')
    for c in clients.data:
        print(f'   - {c["id"]}: {c["name"]} {c["logo"]}')


def main():
    print('=' * 60)
    print('MIGRACAO: Mock -> Supabase (REST API)')
    print('=' * 60)

    supabase = get_client()

    # Verifica se a tabela users existe tentando contar
    try:
        supabase.table('users').select('id', count='exact').limit(1).execute()
    except Exception as e:
        if 'relation' in str(e).lower() and 'does not exist' in str(e).lower():
            print('Tabelas nao existem. Voce precisa rodar o SQL primeiro.')
            create_tables_manually(supabase)
        else:
            print(f'Erro ao verificar tabelas: {e}')
            sys.exit(1)

    insert_initial_data(supabase)
    verify(supabase)

    print()
    print('=' * 60)
    print('[OK] MIGRACAO COMPLETA!')
    print('=' * 60)


if __name__ == '__main__':
    main()
