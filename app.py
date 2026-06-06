"""
Marketing Hub - Patricia's Marketing Agency
Sistema próprio multi-tenant para dashboards de resultados.

Histórico:
- 2026-06-04 (Dia 1): esqueleto + auth + páginas de admin e cliente
- 2026-06-05: deploy no Render.com (free) + feature /change-password
- 2026-06-05: migração pra Supabase via REST API (HTTP, sem pooler)
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from pathlib import Path
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega .env (em dev) — em prod, as env vars vêm do Render
load_dotenv(Path(__file__).parent / '.env')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-trocar-em-producao-2026-change-me')


# ─────────────────────────────────────────────────────────────
# SUPABASE — cliente REST (HTTP, sem precisar de pooler/SSL)
# ─────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://gipuopmdksagqkuuastc.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')  # anon public key

_supabase: Client = None

def get_supabase() -> Client:
    """Inicializa o cliente Supabase (singleton)."""
    global _supabase
    if _supabase is None:
        if not SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_KEY não configurada. "
                "Defina no .env (dev) ou nas env vars do Render (prod)."
            )
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ─────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────

def get_user_by_email(email):
    """Busca usuário pelo email. Retorna dict ou None."""
    try:
        supabase = get_supabase()
        result = supabase.table('users').select('*').eq('email', email.lower()).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        app.logger.error(f'Supabase error in get_user_by_email: {e}')
    return None


def update_user_password(email, new_password_hash):
    """Atualiza a senha do usuário."""
    try:
        supabase = get_supabase()
        supabase.table('users').update(
            {'password_hash': new_password_hash}
        ).eq('email', email.lower()).execute()
        return True
    except Exception as e:
        app.logger.error(f'Supabase error in update_user_password: {e}')
        return False


def get_client_by_id(client_id):
    """Busca cliente pelo id. Retorna dict ou None."""
    try:
        supabase = get_supabase()
        result = supabase.table('clients').select('*').eq('id', client_id).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        app.logger.error(f'Supabase error in get_client_by_id: {e}')
    return None


def get_all_clients():
    """Lista todos os clientes (pro admin)."""
    try:
        supabase = get_supabase()
        result = supabase.table('clients').select('*').order('name').execute()
        return result.data or []
    except Exception as e:
        app.logger.error(f'Supabase error in get_all_clients: {e}')
        return []


# ─────────────────────────────────────────────────────────────
# LEADS HELPERS — módulo de prospecção
# ─────────────────────────────────────────────────────────────

LEAD_STATUSES = [
    'novo',         # acabou de chegar (cold list, sem info)
    'em_contato',   # primeira mensagem enviada
    'coletando',    # lead respondeu, coletando site/IG/GBP
    'analisado',    # info coletada, análise feita
    'proposta',     # proposta enviada
    'ganho',        # virou cliente
    'perdido',      # não quis / não respondeu mais
]

LEAD_STATUS_LABELS = {
    'novo':         ('🆕', 'Novo'),
    'em_contato':   ('📞', 'Em contato'),
    'coletando':    ('💬', 'Coletando info'),
    'analisado':    ('🔍', 'Analisado'),
    'proposta':     ('📄', 'Proposta enviada'),
    'ganho':        ('✅', 'Ganho'),
    'perdido':      ('❌', 'Perdido'),
}


def get_leads(status=None):
    """Lista leads, opcionalmente filtrado por status."""
    try:
        supabase = get_supabase()
        query = supabase.table('leads').select('*').order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        return result.data or []
    except Exception as e:
        app.logger.error(f'Supabase error in get_leads: {e}')
        return []


def get_lead_by_id(lead_id):
    """Busca lead por ID."""
    try:
        supabase = get_supabase()
        result = supabase.table('leads').select('*').eq('id', lead_id).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        app.logger.error(f'Supabase error in get_lead_by_id: {e}')
    return None


def create_lead(data):
    """Cria um lead novo."""
    try:
        supabase = get_supabase()
        result = supabase.table('leads').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        app.logger.error(f'Supabase error in create_lead: {e}')
        return None


def create_leads_bulk(leads_list):
    """Cria vários leads de uma vez (do CSV)."""
    try:
        supabase = get_supabase()
        result = supabase.table('leads').insert(leads_list).execute()
        return len(result.data) if result.data else 0
    except Exception as e:
        app.logger.error(f'Supabase error in create_leads_bulk: {e}')
        return 0


def update_lead(lead_id, data):
    """Atualiza dados de um lead."""
    try:
        supabase = get_supabase()
        result = supabase.table('leads').update(data).eq('id', lead_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        app.logger.error(f'Supabase error in update_lead: {e}')
        return None


def delete_lead(lead_id):
    """Deleta um lead."""
    try:
        supabase = get_supabase()
        supabase.table('leads').delete().eq('id', lead_id).execute()
        return True
    except Exception as e:
        app.logger.error(f'Supabase error in delete_lead: {e}')
        return False


def log_lead_activity(lead_id, activity_type, content=''):
    """Registra uma atividade no log do lead."""
    try:
        supabase = get_supabase()
        supabase.table('lead_activities').insert({
            'lead_id': lead_id,
            'type': activity_type,
            'content': content,
        }).execute()
    except Exception as e:
        app.logger.error(f'Supabase error in log_lead_activity: {e}')


def get_lead_activities(lead_id):
    """Lista atividades de um lead (mais recentes primeiro)."""
    try:
        supabase = get_supabase()
        result = supabase.table('lead_activities').select('*').eq('lead_id', lead_id).order('created_at', desc=True).execute()
        return result.data or []
    except Exception as e:
        app.logger.error(f'Supabase error in get_lead_activities: {e}')
        return []


def get_message_templates(category=None):
    """Lista templates de mensagem."""
    try:
        supabase = get_supabase()
        query = supabase.table('message_templates').select('*').eq('is_active', True).order('category')
        if category:
            query = query.eq('category', category)
        result = query.execute()
        return result.data or []
    except Exception as e:
        app.logger.error(f'Supabase error in get_message_templates: {e}')
        return []


def get_prospection_stats():
    """Calcula métricas de prospecção."""
    try:
        supabase = get_supabase()
        all_leads = supabase.table('leads').select('status, estimated_value, created_at').execute()
        leads = all_leads.data or []

        stats = {
            'total': len(leads),
            'by_status': {s: 0 for s in LEAD_STATUSES},
            'pipeline_value': 0,
            'won_value': 0,
            'won_count': 0,
            'conversion_rate': 0,
        }

        for lead in leads:
            stats['by_status'][lead['status']] = stats['by_status'].get(lead['status'], 0) + 1
            if lead['status'] in ('em_contato', 'coletando', 'analisado', 'proposta'):
                stats['pipeline_value'] += float(lead.get('estimated_value') or 0)
            if lead['status'] == 'ganho':
                stats['won_value'] += float(lead.get('estimated_value') or 0)
                stats['won_count'] += 1

        if stats['total'] > 0:
            stats['conversion_rate'] = round((stats['won_count'] / stats['total']) * 100, 1)

        return stats
    except Exception as e:
        app.logger.error(f'Supabase error in get_prospection_stats: {e}')
        return {'total': 0, 'by_status': {}, 'pipeline_value': 0, 'won_value': 0, 'won_count': 0, 'conversion_rate': 0}


# ─────────────────────────────────────────────────────────────
# CHECKLIST HELPERS — melhorias por cliente
# ─────────────────────────────────────────────────────────────

CHECKLIST_STATUSES = {
    'pending':     ('⏳', 'Pendente'),
    'in_progress': ('🔄', 'Em andamento'),
    'done':        ('✅', 'Concluído'),
    'blocked':     ('🚫', 'Bloqueado'),
}

CHECKLIST_CATEGORIES = {
    'instagram':  ('📱', 'Instagram'),
    'facebook':   ('📘', 'Facebook'),
    'gbp':        ('⭐', 'Google Meu Negócio'),
    'site':       ('🌐', 'Site / Blog'),
    'meta_ads':   ('🎯', 'Meta Ads'),
    'google_ads': ('🔎', 'Google Ads'),
    'reviews':    ('💬', 'Reviews'),
    'custom':     ('📝', 'Customizado'),
}

# Template padrão de auditoria — 32 itens (9 Instagram + 6 Facebook + 7 GBP + 10 Site)
# Vem do ROADMAP-AGENCIA-2026.md (Fase 2). Usado pra popular checklist de qualquer cliente
# após auditoria inicial. Items são marcados com 'from_template' pra distinguir dos custom.
TEMPLATE_CHECKLIST = [
    # Instagram (9)
    ('instagram', 'Bio otimizada (com CTA claro)', 'Bio com proposta de valor + CTA tipo "link pra agendar" ou "chama no DM"'),
    ('instagram', 'Foto de perfil profissional', 'Logo ou foto bem iluminada, sem crop, formato circular ok'),
    ('instagram', 'Destaques salvos e organizados', 'Capa personalizada em cada destaque, ordem lógica (Sobre, Serviços, Depoimentos, etc)'),
    ('instagram', 'Link na bio funcional', 'Linktree ou link direto pro WhatsApp/site funcionando'),
    ('instagram', 'Frequência ≥ 3 posts/semana', 'Mínimo de 3 posts por semana, com mix de formatos'),
    ('instagram', 'Mix de conteúdo (reels, carrossel, stories)', 'Variar entre reels (alcance), carrossel (educação), stories (relacionamento)'),
    ('instagram', 'Hashtags locais + de nicho', 'Mix de hashtags grandes (5), médias (10) e pequenas (15) + locais (cidade/região)'),
    ('instagram', 'Resposta a DMs < 1 hora', 'Tempo de resposta médio inferior a 1h (Meta favorece no algoritmo)'),
    ('instagram', 'ManyChat / resposta automática configurada', 'DM automática quando lead comenta palavra-chave ou manda primeira mensagem'),

    # Facebook (6)
    ('facebook', 'Página completa (about, contact, hours)', 'Todas as seções preenchidas: sobre, contato, horário, endereço, missão'),
    ('facebook', 'Foto de capa profissional', 'Capa 820x312 com chamada visual e CTA'),
    ('facebook', 'Botão de ação configurado', 'Botão "Enviar mensagem", "Ligar" ou "Saiba mais" ativo'),
    ('facebook', 'Reviews respondidos (todos)', 'Resposta em 100% das avaliações, incluindo as negativas'),
    ('facebook', 'Bot de Messenger ativo', 'Resposta automática no Messenger com menu de opções'),
    ('facebook', 'Frequência de post similar ao IG', 'Cruzar conteúdo entre IG e FB (mesma data de post)'),

    # Google Meu Negócio (7)
    ('gbp', 'Perfil 100% preenchido (categorias, descrição, atributos)', 'Categorias principal + secundárias, descrição com palavras-chave, atributos relevantes'),
    ('gbp', 'Horários corretos', 'Horários de funcionamento atualizados, incluindo feriados e exceções'),
    ('gbp', 'Fotos reais (mínimo 10)', 'Fotos do estabelecimento, equipe, produtos/serviços, antes/depois — mínimo 10'),
    ('gbp', 'Posts GBP ativos (≥ 1x/mês)', 'Publicar 1 post por semana (ofertas, eventos, novidades)'),
    ('gbp', 'Reviews respondidos 100%', 'Resposta em todas as avaliações com tom profissional e personalizado'),
    ('gbp', 'Q&A preenchido', 'FAQ no GBP com perguntas frequentes respondidas pelo próprio dono'),
    ('gbp', 'NAP (Nome/Endereço/Telefone) igual ao site', 'Nome, endereço e telefone IDÊNTICOS entre GBP, site, redes sociais e diretórios'),

    # Site / Blog (10)
    ('site', 'Carrega em < 3s no celular', 'Testar com PageSpeed Insights — meta 90+ mobile'),
    ('site', 'SSL ativo (https)', 'Certificado válido, todo o site em HTTPS (sem mixed content)'),
    ('site', 'CTA visível acima da dobra', 'Botão de ação principal no topo da home (WhatsApp, agendar, comprar)'),
    ('site', 'Formulário de contato funcional', 'Formulário envia email ou gera lead no CRM'),
    ('site', 'Google Analytics 4 instalado', 'Tag GA4 no head, eventos de conversão configurados'),
    ('site', 'Schema markup local', 'Schema LocalBusiness com NAP, horários, geo coordinates'),
    ('site', 'Sitemap + robots.txt', 'sitemap.xml atualizado e robots.txt permitindo indexação'),
    ('site', 'Title tag + meta description por página', 'Cada página tem title único + meta description com keyword'),
    ('site', 'Página "sobre" + prova social', 'Página Sobre com história, equipe, depoimentos/clientes'),
    ('site', 'Blog ativo (≥ 1 post/mês)', 'Blog com artigos de SEO local ou autoridade no nicho'),
]


def get_checklist_items(client_id, status=None):
    """Lista checklist items de um cliente, opcionalmente filtrados por status."""
    try:
        supabase = get_supabase()
        query = supabase.table('client_checklist_items').select('*').eq('client_id', client_id).order('created_at', desc=True)
        if status:
            query = query.eq('status', status)
        result = query.execute()
        return result.data or []
    except Exception as e:
        app.logger.error(f'Supabase error in get_checklist_items: {e}')
        return []


def add_checklist_item(client_id, category, title, description=None, priority='medium', assigned_to=None, due_date=None):
    """Adiciona item ao checklist de um cliente."""
    try:
        supabase = get_supabase()
        data = {
            'client_id': client_id,
            'category': category,
            'title': title,
            'status': 'pending',
            'priority': priority,
        }
        if description:
            data['description'] = description
        if assigned_to:
            data['assigned_to'] = assigned_to
        if due_date:
            data['due_date'] = due_date
        result = supabase.table('client_checklist_items').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        app.logger.error(f'Supabase error in add_checklist_item: {e}')
        return None


def update_checklist_item_status(item_id, new_status):
    """Atualiza status de um item do checklist."""
    try:
        supabase = get_supabase()
        data = {'status': new_status, 'updated_at': 'now()'}
        if new_status == 'done':
            data['completed_at'] = 'now()'
        result = supabase.table('client_checklist_items').update(data).eq('id', item_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        app.logger.error(f'Supabase error in update_checklist_item_status: {e}')
        return None


def delete_checklist_item(item_id):
    """Deleta item do checklist."""
    try:
        supabase = get_supabase()
        supabase.table('client_checklist_items').delete().eq('id', item_id).execute()
        return True
    except Exception as e:
        app.logger.error(f'Supabase error in delete_checklist_item: {e}')
        return False


def get_client_checklist_stats(client_id):
    """Calcula progresso do checklist de um cliente."""
    items = get_checklist_items(client_id)
    total = len(items)
    done = sum(1 for i in items if i['status'] == 'done')
    in_progress = sum(1 for i in items if i['status'] == 'in_progress')
    blocked = sum(1 for i in items if i['status'] == 'blocked')
    pending = total - done - in_progress - blocked
    pct = (done / total * 100) if total > 0 else 0
    return {
        'total': total,
        'done': done,
        'in_progress': in_progress,
        'blocked': blocked,
        'pending': pending,
        'pct': round(pct, 0),
    }


def populate_client_checklist_from_template(client_id, replace=False):
    """Popula o checklist de um cliente com os 32 itens padrão do template.

    Args:
        client_id: ID do cliente
        replace: se True, deleta itens existentes com 'from_template' e repopula.
                 se False (default), pula itens cujo título já existe (idempotente).

    Returns:
        dict com {added, skipped, total_template}
    """
    try:
        supabase = get_supabase()

        if replace:
            # Deleta todos os itens do template (mantém os custom)
            supabase.table('client_checklist_items') \
                .delete() \
                .eq('client_id', client_id) \
                .filter('notes', 'eq', 'from_template') \
                .execute()

        # Busca títulos já existentes pra não duplicar
        existing = get_checklist_items(client_id)
        existing_titles = {i['title'] for i in existing}

        added = 0
        skipped = 0
        for category, title, description in TEMPLATE_CHECKLIST:
            if title in existing_titles and not replace:
                skipped += 1
                continue
            data = {
                'client_id': client_id,
                'category': category,
                'title': title,
                'description': description,
                'status': 'pending',
                'priority': 'medium',
                'notes': 'from_template',  # marca pra distinguir de itens custom
            }
            supabase.table('client_checklist_items').insert(data).execute()
            added += 1

        return {
            'added': added,
            'skipped': skipped,
            'total_template': len(TEMPLATE_CHECKLIST),
        }
    except Exception as e:
        app.logger.error(f'Supabase error in populate_client_checklist_from_template: {e}')
        return {'added': 0, 'skipped': 0, 'total_template': len(TEMPLATE_CHECKLIST), 'error': str(e)}


def get_all_clients_checklist_overview():
    """Visão agregada: todos os clientes com progresso do checklist + stats por categoria.

    Retorna lista ordenada por % de progresso (mais atrasado primeiro),
    com contagem por status e por categoria pra cada cliente.
    """
    try:
        supabase = get_supabase()
        clients = supabase.table('clients').select('*').order('name').execute().data or []

        overview = []
        total_done_agg = 0
        total_items_agg = 0
        total_blocked_agg = 0

        for c in clients:
            items = get_checklist_items(c['id'])
            stats = get_client_checklist_stats(c['id'])

            # Breakdown por categoria
            by_category = {}
            for cat in CHECKLIST_CATEGORIES.keys():
                cat_items = [i for i in items if i['category'] == cat]
                cat_done = sum(1 for i in cat_items if i['status'] == 'done')
                by_category[cat] = {
                    'total': len(cat_items),
                    'done': cat_done,
                    'pct': round((cat_done / len(cat_items) * 100) if cat_items else 0, 0),
                }

            overview.append({
                'id': c['id'],
                'name': c['name'],
                'logo': c.get('logo') or '🏢',
                'color': c.get('color') or '#6366f1',
                'paid_traffic': c.get('paid_traffic', False),
                'notes': c.get('notes', ''),
                'stats': stats,
                'by_category': by_category,
            })

            total_done_agg += stats['done']
            total_items_agg += stats['total']
            total_blocked_agg += stats['blocked']

        # Ordena por % feito ASC (mais atrasado primeiro) — depois Patricia pode reordenar
        overview.sort(key=lambda x: (x['stats']['pct'], -x['stats']['total']))

        return {
            'clients': overview,
            'aggregate': {
                'total_clients': len(clients),
                'total_items': total_items_agg,
                'total_done': total_done_agg,
                'total_blocked': total_blocked_agg,
                'avg_pct': round((total_done_agg / total_items_agg * 100) if total_items_agg > 0 else 0, 0),
            },
        }
    except Exception as e:
        app.logger.error(f'Supabase error in get_all_clients_checklist_overview: {e}')
        return {
            'clients': [],
            'aggregate': {
                'total_clients': 0,
                'total_items': 0,
                'total_done': 0,
                'total_blocked': 0,
                'avg_pct': 0,
            },
        }


def find_checklist_item_by_text(client_id, search_text):
    """Encontra item do checklist por match parcial do título (case-insensitive).

    Usado pelo helper de chat: Patricia fala "marquei o item de bio do Instagram
    do EconoClub" e eu acho o item real.
    """
    items = get_checklist_items(client_id)
    search_lower = search_text.lower().strip()

    # Match exato primeiro
    for item in items:
        if search_lower == item['title'].lower():
            return item

    # Match parcial (substring)
    matches = []
    for item in items:
        if search_lower in item['title'].lower():
            matches.append(item)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return matches  # ambíguo, retorna lista pra Patricia escolher

    # Match por palavras-chave (cada palavra deve aparecer)
    keywords = search_lower.split()
    matches = []
    for item in items:
        title_lower = item['title'].lower()
        if all(kw in title_lower for kw in keywords if len(kw) > 3):
            matches.append(item)

    return matches if matches else None


# ─────────────────────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────────────────────

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/')
def home():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_home'))
    return redirect(url_for('client_home'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = get_user_by_email(email)
        if user and check_password_hash(user.get('password_hash', ''), password):
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['role'] = user['role']
            session['client_id'] = user.get('client_id')
            return redirect(url_for('home'))

        flash('Email ou senha incorretos.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        user_email = session.get('user_email')
        user = get_user_by_email(user_email)

        if not user or not check_password_hash(user.get('password_hash', ''), current_pw):
            flash('Current password is incorrect.', 'error')
            return render_template('change_password.html')

        if new_pw != confirm_pw:
            flash('New password and confirmation do not match.', 'error')
            return render_template('change_password.html')

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return render_template('change_password.html')

        new_hash = generate_password_hash(new_pw)
        if update_user_password(user_email, new_hash):
            flash('Password changed successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Error updating password. Please try again.', 'error')
            return render_template('change_password.html')

    return render_template('change_password.html')


@app.route('/admin')
@login_required
@admin_required
def admin_home():
    clients_list = get_all_clients()
    clients_dict = {}
    for c in clients_list:
        checklist = c.get('checklist_data') or {}
        clients_dict[c['id']] = {
            'name': c['name'],
            'logo': c.get('logo') or '🏢',
            'color': c.get('color') or '#6366f1',
            'paid_traffic': c.get('paid_traffic', False),
            'notes': c.get('notes', ''),
            'checklist': {
                'total': checklist.get('total', 0),
                'done': checklist.get('done', 0),
                'in_progress': checklist.get('in_progress', 0),
                'file': checklist.get('file', ''),
                'logo_path': c.get('logo_path', ''),
            },
        }
    return render_template(
        'admin_home.html',
        clients=clients_dict,
        user_name=session.get('user_name'),
        now=datetime.now(),
    )


@app.route('/cliente')
@login_required
def client_home():
    client_id = session.get('client_id')
    client = get_client_by_id(client_id) if client_id else None

    if not client:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('logout'))

    client_view = {
        'name': client['name'],
        'logo': client.get('logo') or '🏢',
        'color': client.get('color') or '#6366f1',
        'paid_traffic': client.get('paid_traffic', False),
        'notes': client.get('notes', ''),
    }
    return render_template(
        'client_home.html',
        client=client_view,
        user_name=session.get('user_name'),
        now=datetime.now(),
    )


# ─────────────────────────────────────────────────────────────
# ROUTES — PROSPECÇÃO
# ─────────────────────────────────────────────────────────────

@app.route('/admin/prospection')
@login_required
@admin_required
def prospection_dashboard():
    """Dashboard de prospecção — métricas + leads recentes."""
    stats = get_prospection_stats()
    leads_recent = get_leads()[:10]  # 10 mais recentes
    return render_template(
        'prospection_dashboard.html',
        stats=stats,
        leads_recent=leads_recent,
        status_labels=LEAD_STATUS_LABELS,
        user_name=session.get('user_name'),
    )


@app.route('/admin/leads')
@login_required
@admin_required
def leads_list():
    """Kanban de leads (cold outreach + CRM)."""
    all_leads = get_leads()
    # Agrupa por status
    leads_by_status = {s: [] for s in LEAD_STATUSES}
    for lead in all_leads:
        leads_by_status[lead['status']].append(lead)

    return render_template(
        'leads_list.html',
        leads_by_status=leads_by_status,
        status_labels=LEAD_STATUS_LABELS,
        statuses=LEAD_STATUSES,
        total=len(all_leads),
        user_name=session.get('user_name'),
    )


@app.route('/admin/leads/new', methods=['GET', 'POST'])
@login_required
@admin_required
def lead_new():
    """Form pra adicionar 1 lead novo."""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        if not phone:
            flash('Telefone é obrigatório.', 'error')
            return render_template('lead_new.html', user_name=session.get('user_name'))

        data = {
            'phone': phone,
            'name': request.form.get('name', '').strip() or None,
            'email': request.form.get('email', '').strip() or None,
            'city': request.form.get('city', '').strip() or None,
            'address': request.form.get('address', '').strip() or None,
            'source': 'manual',
            'status': 'novo',
        }
        # Tags (CSV → array)
        tags_str = request.form.get('tags', '').strip()
        if tags_str:
            data['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]

        # Valor estimado
        ev = request.form.get('estimated_value', '').strip()
        if ev:
            try:
                data['estimated_value'] = float(ev)
            except ValueError:
                pass

        lead = create_lead(data)
        if lead:
            log_lead_activity(lead['id'], 'created', f"Lead criado via form manual. Tags: {tags_str or 'nenhuma'}")
            flash(f'Lead {phone} criado!', 'success')
            return redirect(url_for('lead_detail', lead_id=lead['id']))
        else:
            flash('Erro ao criar lead. Tenta de novo.', 'error')

    return render_template('lead_new.html', user_name=session.get('user_name'))


@app.route('/admin/leads/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def leads_upload():
    """Upload de CSV com telefones."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('leads_upload'))

        file = request.files['file']
        if not file.filename.endswith('.csv'):
            flash('Por favor envie um arquivo .csv', 'error')
            return redirect(url_for('leads_upload'))

        # Parse CSV
        import csv
        from io import StringIO

        content = file.read().decode('utf-8-sig')  # Remove BOM se tiver
        reader = csv.DictReader(StringIO(content))

        leads_to_create = []
        skipped = 0
        for row in reader:
            phone = (row.get('phone') or row.get('telefone') or '').strip()
            if not phone:
                skipped += 1
                continue

            lead_data = {
                'phone': phone,
                'name': (row.get('name') or row.get('nome') or '').strip() or None,
                'email': (row.get('email') or '').strip() or None,
                'city': (row.get('city') or row.get('cidade') or '').strip() or None,
                'address': (row.get('address') or row.get('endereco') or '').strip() or None,
                'source': 'csv_upload',
                'status': 'novo',
            }

            # Tags (se vier)
            tags_str = (row.get('tags') or '').strip()
            if tags_str:
                lead_data['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]

            # Valor estimado
            ev = (row.get('estimated_value') or row.get('valor') or '').strip()
            if ev:
                try:
                    lead_data['estimated_value'] = float(ev)
                except ValueError:
                    pass

            leads_to_create.append(lead_data)

        if not leads_to_create:
            flash(f'Nenhum lead válido encontrado no CSV. {skipped} ignorados.', 'error')
            return redirect(url_for('leads_upload'))

        created = create_leads_bulk(leads_to_create)
        if created > 0:
            flash(f'✅ {created} leads criados com sucesso!', 'success')
            return redirect(url_for('leads_list'))
        else:
            flash('Erro ao criar leads em lote.', 'error')

    return render_template('leads_upload.html', user_name=session.get('user_name'))


@app.route('/admin/leads/<lead_id>')
@login_required
@admin_required
def lead_detail(lead_id):
    """Detalhe de um lead + log de atividades + mudança de status."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        flash('Lead não encontrado.', 'error')
        return redirect(url_for('leads_list'))

    activities = get_lead_activities(lead_id)
    templates = get_message_templates()

    return render_template(
        'lead_detail.html',
        lead=lead,
        activities=activities,
        templates=templates,
        status_labels=LEAD_STATUS_LABELS,
        statuses=LEAD_STATUSES,
        user_name=session.get('user_name'),
    )


@app.route('/admin/leads/<lead_id>/status', methods=['POST'])
@login_required
@admin_required
def lead_update_status(lead_id):
    """Muda o status do lead (vindo de botões no Kanban)."""
    new_status = request.form.get('status', '')
    if new_status not in LEAD_STATUSES:
        flash('Status inválido.', 'error')
        return redirect(url_for('lead_detail', lead_id=lead_id))

    lead = get_lead_by_id(lead_id)
    if not lead:
        flash('Lead não encontrado.', 'error')
        return redirect(url_for('leads_list'))

    old_status = lead['status']
    update_lead(lead_id, {'status': new_status, 'last_contact_at': 'now()'})

    emoji_old, _ = LEAD_STATUS_LABELS[old_status]
    emoji_new, label_new = LEAD_STATUS_LABELS[new_status]
    log_lead_activity(lead_id, 'status_change', f"{emoji_old} {old_status} → {emoji_new} {new_status}")

    flash(f'Status atualizado: {emoji_new} {label_new}', 'success')
    return redirect(url_for('lead_detail', lead_id=lead_id))


@app.route('/admin/leads/<lead_id>/update', methods=['POST'])
@login_required
@admin_required
def lead_update_info(lead_id):
    """Atualiza info do lead (site, IG, FB, GBP, notas)."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        flash('Lead não encontrado.', 'error')
        return redirect(url_for('leads_list'))

    updates = {}
    for field in ['name', 'email', 'city', 'address', 'website', 'instagram', 'facebook', 'google_business_url', 'notes']:
        value = request.form.get(field, '').strip()
        if value:
            updates[field] = value

    ev = request.form.get('estimated_value', '').strip()
    if ev:
        try:
            updates['estimated_value'] = float(ev)
        except ValueError:
            pass

    tags_str = request.form.get('tags', '').strip()
    if tags_str:
        updates['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]

    if updates:
        update_lead(lead_id, updates)
        # Log mudanças significativas
        changed = ', '.join(updates.keys())
        log_lead_activity(lead_id, 'info_added', f"Campos atualizados: {changed}")
        flash('Informações atualizadas!', 'success')

    return redirect(url_for('lead_detail', lead_id=lead_id))


@app.route('/admin/leads/<lead_id>/note', methods=['POST'])
@login_required
@admin_required
def lead_add_note(lead_id):
    """Adiciona nota ao lead."""
    note = request.form.get('note', '').strip()
    if note:
        log_lead_activity(lead_id, 'note', note)
        flash('Nota adicionada.', 'success')
    return redirect(url_for('lead_detail', lead_id=lead_id))


@app.route('/admin/leads/<lead_id>/message', methods=['POST'])
@login_required
@admin_required
def lead_log_message(lead_id):
    """Registra que uma mensagem foi enviada."""
    channel = request.form.get('channel', 'whatsapp')
    template_id = request.form.get('template_id', '')
    content = request.form.get('content', '').strip()

    if not content:
        flash('Mensagem vazia.', 'error')
        return redirect(url_for('lead_detail', lead_id=lead_id))

    log_lead_activity(lead_id, 'message_sent', f"[{channel.upper()}] {content[:200]}")
    update_lead(lead_id, {'last_contact_at': 'now()'})

    # Se tava "novo", muda pra "em_contato"
    lead = get_lead_by_id(lead_id)
    if lead and lead['status'] == 'novo':
        update_lead(lead_id, {'status': 'em_contato'})
        log_lead_activity(lead_id, 'status_change', 'novo → em_contato')

    flash('Mensagem registrada!', 'success')
    return redirect(url_for('lead_detail', lead_id=lead_id))


@app.route('/admin/leads/<lead_id>/delete', methods=['POST'])
@login_required
@admin_required
def lead_delete(lead_id):
    """Deleta um lead."""
    if delete_lead(lead_id):
        flash('Lead deletado.', 'success')
    else:
        flash('Erro ao deletar.', 'error')
    return redirect(url_for('leads_list'))


# ─────────────────────────────────────────────────────────────
# ROUTES — CHECKLIST DE MELHORIAS POR CLIENTE
# ─────────────────────────────────────────────────────────────

@app.route('/admin/clientes/<client_id>/checklist', methods=['GET', 'POST'])
@login_required
@admin_required
def client_checklist(client_id):
    """Lista de melhorias do cliente + adicionar novo item."""
    client = get_client_by_id(client_id)
    if not client:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('admin_home'))

    if request.method == 'POST':
        # Adicionar novo item
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'custom')
        if title:
            add_checklist_item(
                client_id=client_id,
                category=category,
                title=title,
                description=request.form.get('description', '').strip() or None,
                priority=request.form.get('priority', 'medium'),
                assigned_to=request.form.get('assigned_to', '').strip() or None,
            )
            flash(f'✅ Item "{title}" adicionado!', 'success')
        return redirect(url_for('client_checklist', client_id=client_id))

    items = get_checklist_items(client_id)
    stats = get_client_checklist_stats(client_id)
    # Verifica se já tem itens do template (pra mostrar/esconder botão de auditar)
    has_template = any(i.get('notes') == 'from_template' for i in items)
    return render_template(
        'client_checklist.html',
        client=client,
        items=items,
        stats=stats,
        status_labels=CHECKLIST_STATUSES,
        category_labels=CHECKLIST_CATEGORIES,
        has_template_items=has_template,
        user_name=session.get('user_name'),
    )


@app.route('/admin/clientes/<client_id>/checklist/auditar', methods=['POST'])
@login_required
@admin_required
def client_checklist_auditar(client_id):
    """Popula o checklist do cliente com os 32 itens padrão do template."""
    client = get_client_by_id(client_id)
    if not client:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('admin_home'))

    replace = request.form.get('replace', 'false') == 'true'
    result = populate_client_checklist_from_template(client_id, replace=replace)

    if result.get('error'):
        flash(f'❌ Erro ao popular template: {result["error"]}', 'error')
    elif replace:
        flash(f'🌱 Template repopulado! {result["added"]} itens adicionados (substituindo anteriores).', 'success')
    else:
        flash(f'🌱 {result["added"]} itens adicionados do template! ({result["skipped"]} já existiam — não duplicados)', 'success')

    return redirect(url_for('client_checklist', client_id=client_id))


@app.route('/admin/checklist-overview')
@login_required
@admin_required
def checklist_overview():
    """Visão geral de TODOS os clientes com seus checklists (ranking)."""
    sort = request.args.get('sort', 'atrasado')  # 'atrasado' | 'avancado' | 'nome' | 'bloqueado'
    category_filter = request.args.get('category', '')

    overview = get_all_clients_checklist_overview()
    clients_list = overview['clients']

    # Aplica filtro/ordenação
    if sort == 'avancado':
        clients_list.sort(key=lambda x: -x['stats']['pct'])
    elif sort == 'nome':
        clients_list.sort(key=lambda x: x['name'].lower())
    elif sort == 'bloqueado':
        clients_list.sort(key=lambda x: -x['stats']['blocked'])
    # default: 'atrasado' (já vem ordenado do helper)

    return render_template(
        'checklist_overview.html',
        clients=clients_list,
        aggregate=overview['aggregate'],
        category_labels=CHECKLIST_CATEGORIES,
        sort=sort,
        category_filter=category_filter,
        user_name=session.get('user_name'),
    )


@app.route('/admin/checklist/<item_id>/status', methods=['POST'])
@login_required
@admin_required
def checklist_update_status(item_id):
    """Marca item como feito, em andamento, etc."""
    new_status = request.form.get('status', '')
    if new_status not in CHECKLIST_STATUSES:
        flash('Status inválido.', 'error')
        return redirect(request.referrer or url_for('admin_home'))

    # Buscar item pra pegar o client_id pro redirect
    try:
        supabase = get_supabase()
        item = supabase.table('client_checklist_items').select('client_id').eq('id', item_id).execute()
        client_id = item.data[0]['client_id'] if item.data else None
    except Exception:
        client_id = None

    update_checklist_item_status(item_id, new_status)
    emoji, label = CHECKLIST_STATUSES[new_status]
    flash(f'{emoji} Item marcado: {label}', 'success')

    if client_id:
        return redirect(url_for('client_checklist', client_id=client_id))
    return redirect(url_for('admin_home'))


@app.route('/admin/checklist/<item_id>/delete', methods=['POST'])
@login_required
@admin_required
def checklist_delete(item_id):
    """Deleta item do checklist."""
    try:
        supabase = get_supabase()
        item = supabase.table('client_checklist_items').select('client_id').eq('id', item_id).execute()
        client_id = item.data[0]['client_id'] if item.data else None
    except Exception:
        client_id = None

    delete_checklist_item(item_id)
    flash('Item removido.', 'success')

    if client_id:
        return redirect(url_for('client_checklist', client_id=client_id))
    return redirect(url_for('admin_home'))


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'

    if SUPABASE_KEY:
        try:
            get_supabase()
            print('OK Conexao com Supabase REST estabelecida')
        except Exception as e:
            print(f'ERRO Supabase: {e}')
    else:
        print('AVISO: SUPABASE_KEY nao configurada.')

    app.run(debug=debug, host='0.0.0.0', port=port)
