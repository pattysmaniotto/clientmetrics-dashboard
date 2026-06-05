"""
Marketing Hub - Patricia's Marketing Agency
Sistema próprio multi-tenant para dashboards de resultados.

Histórico:
- 2026-06-04 (Dia 1): esqueleto + auth + páginas de admin e cliente
- 2026-06-05: deploy no Render.com (free) + feature /change-password
- 2026-06-05: migração pra Supabase (Postgres) — senhas persistem!
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from contextlib import contextmanager
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-trocar-em-producao-2026-change-me')


# ─────────────────────────────────────────────────────────────
# DATABASE — Supabase (Postgres) com connection pool
# ─────────────────────────────────────────────────────────────

DB_URL = os.environ.get('DATABASE_URL')
_pool = None

def init_pool():
    """Inicializa o pool de conexões. Chamado 1x no startup."""
    global _pool
    if _pool is not None:
        return _pool
    if not DB_URL:
        raise RuntimeError(
            "DATABASE_URL não configurada. "
            "Configure no .env (dev) ou nas env vars do Render (prod)."
        )
    _pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=DB_URL,
        sslmode='require',  # Supabase exige SSL
    )
    return _pool

@contextmanager
def get_db():
    """Context manager que pega conexão do pool e devolve no fim."""
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def query_one(sql, params=()):
    """SELECT que retorna 1 linha (dict) ou None."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def query_all(sql, params=()):
    """SELECT que retorna todas as linhas (lista de dicts)."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def execute(sql, params=()):
    """INSERT/UPDATE/DELETE que não retorna dados."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


# ─────────────────────────────────────────────────────────────
# DATA HELPERS — users e clients (substituem os dicts antigos)
# ─────────────────────────────────────────────────────────────

def get_user_by_email(email):
    """Busca usuário pelo email. Retorna dict ou None."""
    return query_one(
        "SELECT id, email, password_hash, role, name, client_id "
        "FROM users WHERE email = %s",
        (email.lower(),)
    )


def get_user_by_id(user_id):
    return query_one(
        "SELECT id, email, password_hash, role, name, client_id "
        "FROM users WHERE id = %s",
        (user_id,)
    )


def update_user_password(email, new_password_hash):
    return execute(
        "UPDATE users SET password_hash = %s WHERE email = %s",
        (new_password_hash, email.lower())
    )


def get_client_by_id(client_id):
    """Busca cliente pelo id. Retorna dict ou None."""
    return query_one(
        "SELECT id, name, logo, color, paid_traffic, notes, "
        "checklist_data, logo_path "
        "FROM clients WHERE id = %s",
        (client_id,)
    )


def get_all_clients():
    """Lista todos os clientes (pro admin)."""
    return query_all(
        "SELECT id, name, logo, color, paid_traffic, notes, "
        "checklist_data, logo_path "
        "FROM clients ORDER BY name"
    )


# ─────────────────────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
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
        try:
            user = get_user_by_email(email)
        except Exception as e:
            app.logger.error(f'Database error during login: {e}')
            flash('Erro temporário no servidor. Tenta de novo em 30s.', 'error')
            return render_template('login.html')

        if user and check_password_hash(user['password_hash'], password):
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
        try:
            user = get_user_by_email(user_email)
        except Exception as e:
            app.logger.error(f'Database error in change_password: {e}')
            flash('Erro temporário no servidor. Tenta de novo.', 'error')
            return render_template('change_password.html')

        if not user or not check_password_hash(user['password_hash'], current_pw):
            flash('Current password is incorrect.', 'error')
            return render_template('change_password.html')

        if new_pw != confirm_pw:
            flash('New password and confirmation do not match.', 'error')
            return render_template('change_password.html')

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return render_template('change_password.html')

        # Update no banco
        try:
            update_user_password(user_email, generate_password_hash(new_pw))
        except Exception as e:
            app.logger.error(f'Database error updating password: {e}')
            flash('Erro ao atualizar senha. Tenta de novo.', 'error')
            return render_template('change_password.html')

        flash('Password changed successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('change_password.html')


@app.route('/admin')
@login_required
@admin_required
def admin_home():
    try:
        clients_list = get_all_clients()
        # Converte cada linha num dict com 'checklist' parseado
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
    except Exception as e:
        app.logger.error(f'Database error in admin_home: {e}')
        flash('Erro ao carregar clientes. Tenta de novo.', 'error')
        clients_dict = {}

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
    try:
        client = get_client_by_id(client_id) if client_id else None
    except Exception as e:
        app.logger.error(f'Database error in client_home: {e}')
        flash('Erro ao carregar dados. Tenta de novo.', 'error')
        return redirect(url_for('logout'))

    if not client:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('logout'))

    checklist = client.get('checklist_data') or {}

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

    # Inicializa o pool de conexões
    if DB_URL:
        try:
            init_pool()
            print('✓ Conexão com o banco estabelecida (Supabase)')
        except Exception as e:
            print(f'⚠️ Erro ao conectar no banco: {e}')
            print('  Verifique se DATABASE_URL está configurada corretamente.')
    else:
        print('⚠️ DATABASE_URL não configurada.')
        print('  Defina no .env ou como variável de ambiente.')

    app.run(debug=debug, host='0.0.0.0', port=port)
