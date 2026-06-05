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
