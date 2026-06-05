"""
Marketing Hub - Patricia's Marketing Agency
Sistema próprio multi-tenant para dashboards de resultados.

Dia 1 (2026-06-04): esqueleto + auth básica + páginas de admin e cliente.
Dados ainda são mock. Banco e integrações vêm nas próximas sessões.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-trocar-em-producao-2026-change-me')


# ─────────────────────────────────────────────────────────────
# MOCK DATA — substituir por banco de dados nas próximas sessões
# ─────────────────────────────────────────────────────────────

USERS = {
    'patricia@agencia.com': {
        'password': generate_password_hash('admin123'),
        'role': 'admin',
        'name': 'Patricia',
    },
    'econoclub@cliente.com': {
        'password': generate_password_hash('cliente123'),
        'role': 'client',
        'name': 'EconoClub',
        'client_id': 'econoclub',
    },
    'benalex@cliente.com': {
        'password': generate_password_hash('cliente123'),
        'role': 'client',
        'name': 'Benalex Cleaning',
        'client_id': 'benalex',
    },
    'dyemys@cliente.com': {
        'password': generate_password_hash('cliente123'),
        'role': 'client',
        'name': "DYEMY'S Painting",
        'client_id': 'dyemys',
    },
}

CLIENTS = {
    'econoclub': {
        'name': 'EconoClub',
        'logo': '🌱',
        'color': '#10b981',
        'paid_traffic': False,  # sem tráfego pago rodando no momento
        'notes': 'Cliente-piloto da Fase 1. Migração Square → Stripe em andamento.',
        'checklist': {
            'total': 32,
            'done': 0,
            'in_progress': 0,
            'file': 'CLIENTES/ECONOCLUB/CHECKLIST.md',
        },
    },
    'benalex': {
        'name': 'Benalex Cleaning Services',
        'logo': '🧹',
        'color': '#0099ff',
        'paid_traffic': False,
        'notes': 'GBP FINALIZADO 04/06. Endereço escondido (service area). 5 fotos enviadas (4 IA + logo). Descrição + serviços em inglês. Pronto pra entregar pro cliente.',
        'checklist': {
            'total': 41,
            'done': 6,
            'in_progress': 0,
            'file': 'CLIENTES/BENALEX/CHECKLIST.md',
            'logo_path': '../BENALEX/logo.png',
        },
    },
    'dyemys': {
        'name': "DYEMY'S Painting",
        'logo': '🎨',
        'color': '#1a2e4a',
        'paid_traffic': False,
        'notes': 'GBP FINALIZADO 04/06. Sem endereço (já correto). 5 fotos enviadas (4 IA + logo). Descrição + serviços em inglês. Pronto pra entregar pro cliente.',
        'checklist': {
            'total': 41,
            'done': 6,
            'in_progress': 0,
            'file': 'CLIENTES/DYEMYS/CHECKLIST.md',
            'logo_path': '../DYEMYS/logo.jpg',
        },
    },
}


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
        user = USERS.get(email)
        if user and check_password_hash(user['password'], password):
            session['user_email'] = email
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
        user = USERS.get(user_email)

        if not user or not check_password_hash(user['password'], current_pw):
            flash('Current password is incorrect.', 'error')
            return render_template('change_password.html')

        if new_pw != confirm_pw:
            flash('New password and confirmation do not match.', 'error')
            return render_template('change_password.html')

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return render_template('change_password.html')

        # Update the password in memory
        USERS[user_email]['password'] = generate_password_hash(new_pw)
        flash('Password changed successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('change_password.html')


@app.route('/admin')
@login_required
@admin_required
def admin_home():
    return render_template(
        'admin_home.html',
        clients=CLIENTS,
        user_name=session.get('user_name'),
        now=datetime.now(),
    )


@app.route('/cliente')
@login_required
def client_home():
    client_id = session.get('client_id')
    if not client_id or client_id not in CLIENTS:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('logout'))
    client = CLIENTS[client_id]
    return render_template(
        'client_home.html',
        client=client,
        user_name=session.get('user_name'),
        now=datetime.now(),
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
