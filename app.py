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
