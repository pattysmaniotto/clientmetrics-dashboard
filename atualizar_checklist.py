"""
atualizar_checklist.py
======================
Helper de CHAT pra Patricia atualizar o checklist de um cliente SEM precisar
abrir o painel. Roda direto no terminal.

Uso (3 jeitos):
    # Jeito 1 — buscar por trecho do título e marcar como done
    python atualizar_checklist.py "EconoClub" "bio" done

    # Jeito 2 — listar itens pendentes de um cliente
    python atualizar_checklist.py "EconoClub" list

    # Jeito 3 — adicionar item custom
    python atualizar_checklist.py "EconoClub" add "Responder 3 reviews negativos" reviews high

    # Jeito 4 — popular template (auditoria inicial)
    python atualizar_checklist.py "EconoClub" auditar

Status aceitos: pending, in_progress, done, blocked
Prioridades: low, medium, high, urgent
Categorias: instagram, facebook, gbp, site, meta_ads, google_ads, reviews, custom
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Carrega .env (em dev)
load_dotenv(Path(__file__).parent / '.env')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://gipuopmdksagqkuuastc.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_KEY:
    print('❌ SUPABASE_KEY não configurada no .env')
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def find_client(name_or_id):
    """Busca cliente por nome (parcial) ou ID exato."""
    # Tenta ID exato primeiro
    r = supabase.table('clients').select('*').eq('id', name_or_id).execute()
    if r.data:
        return r.data[0]

    # Busca por nome (case-insensitive)
    name_lower = name_or_id.lower()
    r = supabase.table('clients').select('*').execute()
    matches = [c for c in (r.data or []) if name_lower in c['name'].lower()]

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f'⚠️  Vários clientes encontrados com "{name_or_id}":')
        for c in matches:
            print(f'  - {c["name"]} (id: {c["id"]})')
        print('   Seja mais específica ou use o id.')
        return None
    print(f'❌ Nenhum cliente encontrado com "{name_or_id}"')
    return None


def find_item(client_id, search_text):
    """Busca item do checklist por match do título."""
    r = supabase.table('client_checklist_items').select('*').eq('client_id', client_id).execute()
    items = r.data or []
    search_lower = search_text.lower().strip()

    # Match exato
    for item in items:
        if search_lower == item['title'].lower():
            return item

    # Match parcial
    matches = [i for i in items if search_lower in i['title'].lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f'⚠️  Vários itens encontrados com "{search_text}":')
        for i in matches:
            print(f'  - [{i["status"]}] {i["title"]}  (id: {i["id"]})')
        return None
    return None


def cmd_status(client_name, search_text, new_status):
    """Marca um item como novo status."""
    if new_status not in ('pending', 'in_progress', 'done', 'blocked'):
        print(f'❌ Status inválido: {new_status}')
        print('   Use: pending, in_progress, done, blocked')
        return

    client = find_client(client_name)
    if not client:
        return

    item = find_item(client['id'], search_text)
    if not item:
        print(f'❌ Nenhum item do {client["name"]} combina com "{search_text}"')
        return

    data = {'status': new_status, 'updated_at': 'now()'}
    if new_status == 'done':
        data['completed_at'] = 'now()'

    supabase.table('client_checklist_items').update(data).eq('id', item['id']).execute()

    emoji = {'pending': '⏳', 'in_progress': '🔄', 'done': '✅', 'blocked': '🚫'}[new_status]
    print(f'{emoji} Item "{item["title"]}" do {client["name"]} → {new_status}')


def cmd_list(client_name, status_filter=None):
    """Lista itens do checklist de um cliente."""
    client = find_client(client_name)
    if not client:
        return

    r = supabase.table('client_checklist_items') \
        .select('*') \
        .eq('client_id', client['id']) \
        .order('status') \
        .order('category') \
        .execute()
    items = r.data or []

    if not items:
        print(f'   {client["name"]} não tem itens no checklist ainda.')
        print(f'   Rode: python atualizar_checklist.py "{client["name"]}" auditar')
        return

    print(f'📋 Checklist do {client["name"]} ({len(items)} itens):\n')
    by_status = {'done': [], 'in_progress': [], 'pending': [], 'blocked': []}
    for i in items:
        by_status.setdefault(i['status'], []).append(i)

    for status in ('blocked', 'in_progress', 'pending', 'done'):
        if not by_status.get(status):
            continue
        emoji = {'done': '✅', 'in_progress': '🔄', 'pending': '⏳', 'blocked': '🚫'}[status]
        print(f'{emoji} {status.upper()} ({len(by_status[status])})')
        for i in by_status[status]:
            cat = i.get('category', '?')
            print(f'   [{cat}] {i["title"]}')
        print()


def cmd_add(client_name, title, category='custom', priority='medium'):
    """Adiciona item custom ao checklist."""
    if category not in ('instagram', 'facebook', 'gbp', 'site', 'meta_ads',
                        'google_ads', 'reviews', 'custom'):
        print(f'❌ Categoria inválida: {category}')
        return
    if priority not in ('low', 'medium', 'high', 'urgent'):
        print(f'❌ Prioridade inválida: {priority}')
        return

    client = find_client(client_name)
    if not client:
        return

    data = {
        'client_id': client['id'],
        'category': category,
        'title': title,
        'status': 'pending',
        'priority': priority,
    }
    r = supabase.table('client_checklist_items').insert(data).execute()
    if r.data:
        print(f'✅ Item adicionado ao checklist do {client["name"]}: "{title}"')
    else:
        print('❌ Erro ao adicionar item.')


def cmd_auditar(client_name, replace=False):
    """Popula o checklist do cliente com os 32 itens do template."""
    # Importa o template do app.py
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from app import TEMPLATE_CHECKLIST
    except ImportError:
        print('❌ Não consegui importar TEMPLATE_CHECKLIST do app.py')
        return

    client = find_client(client_name)
    if not client:
        return

    if replace:
        confirm = input(f'⚠️  ISSO DELETA os 32 itens do template do {client["name"]} e repopula. Confirma? (s/n): ')
        if confirm.lower() != 's':
            print('Cancelado.')
            return
        supabase.table('client_checklist_items') \
            .delete() \
            .eq('client_id', client['id']) \
            .filter('notes', 'eq', 'from_template') \
            .execute()

    # Verifica títulos existentes
    existing = supabase.table('client_checklist_items') \
        .select('title') \
        .eq('client_id', client['id']) \
        .execute()
    existing_titles = {i['title'] for i in (existing.data or [])}

    added = 0
    skipped = 0
    for category, title, description in TEMPLATE_CHECKLIST:
        if title in existing_titles and not replace:
            skipped += 1
            continue
        supabase.table('client_checklist_items').insert({
            'client_id': client['id'],
            'category': category,
            'title': title,
            'description': description,
            'status': 'pending',
            'priority': 'medium',
            'notes': 'from_template',
        }).execute()
        added += 1

    print(f'🌱 {client["name"]}: {added} itens adicionados, {skipped} já existiam (não duplicados).')
    print(f'   Agora vá no painel: https://clientmetrics.app/admin/clientes/{client["id"]}/checklist')


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return

    client_name = sys.argv[1]
    action = sys.argv[2].lower()

    if action == 'list':
        cmd_list(client_name)
    elif action in ('pending', 'in_progress', 'done', 'blocked'):
        if len(sys.argv) < 4:
            print('❌ Falta o trecho do título do item.')
            print('   Uso: python atualizar_checklist.py "Cliente" done "trecho do título"')
            return
        search = sys.argv[3]
        cmd_status(client_name, search, action)
    elif action == 'add':
        if len(sys.argv) < 4:
            print('❌ Falta o título do item.')
            return
        title = sys.argv[3]
        category = sys.argv[4] if len(sys.argv) > 4 else 'custom'
        priority = sys.argv[5] if len(sys.argv) > 5 else 'medium'
        cmd_add(client_name, title, category, priority)
    elif action == 'auditar':
        replace = '--replace' in sys.argv
        cmd_auditar(client_name, replace=replace)
    else:
        # Tenta tratar como trecho de item com status "done" (jeito mais comum)
        cmd_status(client_name, action, 'done')


if __name__ == '__main__':
    main()
