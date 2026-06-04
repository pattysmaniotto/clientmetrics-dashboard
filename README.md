# Marketing Hub — Patricia's Marketing Agency

Sistema próprio multi-tenant para dashboards de resultados de clientes.

## 🚀 Como rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Rodar o servidor
```bash
python app.py
```

### 3. Abrir no navegador
http://localhost:5000

## 🔑 Credenciais de teste (Dia 1 — 04/06/2026)

- **Admin (Patricia):** `patricia@agencia.com` / `admin123`
- **Cliente (EconoClub):** `econoclub@cliente.com` / `cliente123`

> ⚠️ Senhas são mock — em produção vão pra banco com hash bcrypt.

## 📁 Estrutura

```
_agencia_dashboard/
├── app.py                    # aplicação Flask principal
├── requirements.txt          # dependências Python
├── README.md                 # este arquivo
├── ROADMAP-...               # (referência externa)
└── templates/
    ├── base.html             # template base (Tailwind via CDN)
    ├── login.html            # tela de login (com gradiente)
    ├── admin_home.html       # painel admin (Patricia)
    └── client_home.html      # painel do cliente (EconoClub)
```

## ✅ O que tá pronto (Dia 1)

- [x] Estrutura do projeto Flask
- [x] Tela de login (bonita, responsiva)
- [x] Painel admin (Patricia) — lista de clientes, KPIs placeholder
- [x] Painel cliente (EconoClub) — KPIs placeholder, status de tráfego
- [x] Auth multi-tenant (admin vs cliente)
- [x] Mensagem amigável quando não tem tráfego pago

## 🛠️ Próximos passos (próximas sessões)

- [ ] Banco de dados (Postgres via Supabase) — substituir USERS/CLIENTS mock
- [ ] Gráficos com Chart.js (linha, barra, donut, funil)
- [ ] Entrada de dados (manual + upload CSV)
- [ ] Integração com Meta Ads API
- [ ] Integração com Google Ads API
- [ ] Integração com Google Analytics 4
- [ ] Integração com Google Meu Negócio
- [ ] Relatório em PDF
- [ ] Deploy em Railway + domínio customizado

## 📍 Roadmap do projeto

Ver: `Desktop/CLIENTES/ROADMAP-AGENCIA-2026.md`

## 🐛 Troubleshooting

**Porta 5000 ocupada?** Edite `app.py` na última linha e troque `port=5000` por outra (ex: 5001).

**Python não encontrado?** Instale Python 3.10+ de https://python.org e marque "Add to PATH" na instalação.

**Tailwind não carrega?** Precisa de internet (Tailwind vem via CDN).
