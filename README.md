# 🧾 NotaTrack SaaS — Controle de Gastos com NFC-e

Uma plataforma web moderna para rastreamento de notas fiscais gaúchas (SEFAZ-RS) com dashboard interativo, autenticação e arquitetura Multi-Tenant para múltiplos usuários.

![NotaTrack SaaS Dashboard](frontend/icon.svg)

## 🚀 Novidades na Versão SaaS

- **Multi-Tenant / Multi-Usuário**: Autenticação completa e segura para múltiplos usuários simultâneos. Suas notas são visíveis apenas por você.
- **Supabase (PostgreSQL)**: Banco de dados relacional robusto na nuvem com **Row Level Security (RLS)**.
- **Frontend Refatorado**: Divisão entre rotas e páginas de autenticação (Login / Registro) de forma elegante e com design moderno escuro (Dark Theme).
- **Pronto para Deploy**: Backend Python Flask e frontend preparado para hospedagem integrada em um único Web Service (Render/Heroku).

## 🛠 Pré-requisitos (Desenvolvimento)

- Python 3.10+
- Conta gratuita no [Supabase](https://supabase.com/)

## ⚙️ Instalação Local

```bash
# 1. Clone o projeto
git clone https://github.com/eduardosouuza/Lista-notas-Tracker.git
cd Lista-notas-Tracker

# 2. Instale as dependências Python
pip install -r requirements.txt

# 3. Instale o Chromium (usado pelo Playwright para o Web Scraping da SEFAZ)
python -m playwright install chromium
python -m playwright install-deps chromium
```

### Configuração do Supabase

1. Crie um projeto no Supabase.
2. Na aba `SQL Editor`, rode o código contido no arquivo `backend/schema.sql` para criar as tabelas `notas` e `produtos` com as políticas de segurança.
3. Ative as inscrições de E-mail: Vá em **Authentication -> Providers -> Email**, ligue "Enable Email Signup" e desative a opção "Confirm email" para testes locais imediatos.
4. Crie um arquivo `.env` dentro da pasta `backend/` com as suas credenciais:

```env
SUPABASE_URL=https://SUA_URL_AQUI.supabase.co
SUPABASE_KEY=SUA_ANON_KEY_AQUI
```

## ▶️ Rodando Localmente

```bash
# Inicie o servidor Flask (ele servirá automaticamente o frontend via pasta estática)
python backend/server.py
```

Acesse: **http://localhost:5000**
Faça o registro de sua nova conta na página de login e comece a rastrear!

## 🌐 Como fazer o Deploy na Nuvem (Render)

Como o Flask serve os arquivos estáticos diretamente pela raiz `/`, você pode hospedar o frontend e backend usando um único serviço gratuito no Render.com.

1. Suba seu código para o GitHub.
2. No [Render](https://render.com/), crie um novo **Web Service** conectado ao seu repositório.
3. Configurações do Render:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python -m playwright install chromium && python -m playwright install-deps chromium`
   - **Start Command**: `cd backend && gunicorn server:app`
4. Na aba **Environment Variables**, adicione suas variáveis: `SUPABASE_URL` e `SUPABASE_KEY`.
5. Salve e deixe o Render aplicar o Build.

## 🗂 Estrutura do Projeto

```
NotaTrack/
├── backend/
│   ├── server.py        ← API Flask (Autenticação JWT, Rotas JSON)
│   ├── scraper.py       ← Playwright + extração HTML (SEFAZ-RS)
│   ├── schema.sql       ← Tabelas PostgreSQL + Row Level Security
│   └── .env             ← Chaves do banco de dados (não commitado)
├── frontend/
│   ├── index.html       ← App Web Principal (Login, Dashboard, Scanner)
│   ├── app.js           ← Integração Supabase Auth e Lógica de negócio
│   └── index.css        ← Design System (Vanilla CSS + UI Premium)
└── requirements.txt     ← Dependências do servidor e build
```

## ⚠️ Resolução de Problemas

**"Falha ao buscar nota na SEFAZ"** → O site oficial às vezes passa por instabilidade ou lentidão no processamento dos QR Codes. Tente novamente após alguns minutos.  
**O Web Scraper quebrou?** → Se o layout da SEFAZ mudar, será necessário adaptar os seletores no `backend/scraper.py`.

## 💻 Tech Stack

- **Backend**: Python 3, Flask, Supabase-py, Playwright (Headless Scraping)
- **Banco de Dados**: PostgreSQL na Nuvem via Supabase com autenticação nativa.
- **Frontend**: HTML5, Vanilla JavaScript, CSS Puro (Custom Variables + Glassmorphism).
- **Métricas**: Chart.js integrado.
- **Scanner**: Html5Qrcode.
