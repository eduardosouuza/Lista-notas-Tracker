import sys, os, json
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from datetime import datetime
try:
    from .scraper import scrape_nota, parse_nota_do_html, limpar_chave
except ImportError:
    from scraper import scrape_nota, parse_nota_do_html, limpar_chave
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__, static_folder='../frontend')
CORS(app)

url: str | None = os.environ.get("SUPABASE_URL")
key: str | None = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("[WARN] SUPABASE_URL e SUPABASE_KEY nao encontrados no ambiente")

supabase: Client | None = create_client(url, key) if url and key else None

# ─────────────── AUTENTICAÇÃO ───────────────

def require_auth():
    if not supabase:
        return None

    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    token = auth_header.replace('Bearer ', '')
    try:
        user_res = supabase.auth.get_user(token)
        request_client = create_client(url, key)
        request_client.postgrest.auth(token)
        g.supabase = request_client
        return user_res.user
    except Exception as e:
        return None


def db_client():
    return getattr(g, 'supabase', supabase)

# ─────────────── HELPERS DE BANCO ───────────────

def salvar_nota_supabase(nota: dict, user_id: str):
    # Verifica se já existe
    db = db_client()
    existente = db.table('notas').select('id').eq('chave', nota['chave']).eq('user_id', user_id).execute()
    if existente.data:
        return existente.data[0]['id']

    # Insere nota
    nova_nota = {
        'user_id': user_id,
        'chave': nota['chave'],
        'emitente': nota['emitente'],
        'cnpj': nota.get('cnpj'),
        'endereco': nota.get('endereco'),
        'data_emissao': nota.get('data_emissao'),
        'numero': nota.get('numero'),
        'valor_total': nota.get('valor_total', 0),
        'url': nota.get('url'),
        'dados_json': json.dumps(nota, ensure_ascii=False)
    }

    res_nota = db.table('notas').insert(nova_nota).execute()
    nota_id = res_nota.data[0]['id']

    # Insere produtos
    produtos = []
    for p in nota.get('produtos', []):
        produtos.append({
            'nota_id': nota_id,
            'nome': p['nome'],
            'qtd': p.get('qtd', 1),
            'valor_unitario': p.get('valor_unitario', 0),
            'valor_total': p.get('valor_total', 0)
        })
    
    if produtos:
        db.table('produtos').insert(produtos).execute()

    return nota_id

# ─────────────── ROTAS API ───────────────

@app.route('/api/notas', methods=['GET'])
def listar_notas():
    user = require_auth()
    if not user: return jsonify({'erro': 'Não autorizado'}), 401

    # Fetch notes
    res = db_client().table('notas').select('*, produtos(id)').eq('user_id', user.id).order('criado_em', desc=True).execute()
    
    notas = []
    for n in res.data:
        n['total_itens'] = len(n.get('produtos', []))
        n.pop('produtos', None)
        n.pop('dados_json', None)
        notas.append(n)
        
    return jsonify(notas)

@app.route('/api/notas/<int:nota_id>', methods=['GET'])
def detalhe_nota(nota_id):
    user = require_auth()
    if not user: return jsonify({'erro': 'Não autorizado'}), 401

    res = db_client().table('notas').select('*, produtos(*)').eq('id', nota_id).eq('user_id', user.id).execute()
    if not res.data:
        return jsonify({'erro': 'Nota não encontrada'}), 404
        
    nota = res.data[0]
    nota.pop('dados_json', None)
    return jsonify(nota)

@app.route('/api/notas/<int:nota_id>', methods=['DELETE'])
def deletar_nota(nota_id):
    user = require_auth()
    if not user: return jsonify({'erro': 'Não autorizado'}), 401

    db_client().table('notas').delete().eq('id', nota_id).eq('user_id', user.id).execute()
    return jsonify({'ok': True})

@app.route('/api/buscar', methods=['POST'])
def buscar_nota():
    user = require_auth()
    if not user: return jsonify({'erro': 'Não autorizado'}), 401

    body = request.get_json()
    entrada = (body or {}).get('chave', '').strip()
    if not entrada:
        return jsonify({'erro': 'Informe a chave ou URL da nota'}), 400

    try:
        chave = limpar_chave(entrada)
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400

    existente = db_client().table('notas').select('id').eq('chave', chave).eq('user_id', user.id).execute()
    if existente.data:
        return jsonify({'erro': 'Nota já cadastrada', 'nota_id': existente.data[0]['id']}), 409

    try:
        raw = scrape_nota(chave)
        nota = parse_nota_do_html(raw)
    except Exception as e:
        return jsonify({'erro': f'Falha ao buscar nota na SEFAZ: {e}'}), 500

    try:
        nota_id = salvar_nota_supabase(nota, user.id)
    except Exception as e:
        return jsonify({'erro': f'Falha ao salvar nota no Supabase: {e}'}), 500
    nota['id'] = nota_id
    return jsonify(nota), 201

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    user = require_auth()
    if not user: return jsonify({'erro': 'Não autorizado'}), 401

    res = db_client().table('notas').select('*, produtos(*)').eq('user_id', user.id).execute()
    notas = res.data
    
    total_gasto = sum(n.get('valor_total') or 0 for n in notas)
    total_notas = len(notas)
    ticket_medio = total_gasto / total_notas if total_notas else 0
    
    meses_dict = {}
    mercados_dict = {}
    produtos_dict = {}
    
    for n in notas:
        # Mes
        d = n.get('data_emissao') or ''
        if len(d) >= 10:
            if d[2] == '/': # DD/MM/YYYY
                mes = f"{d[6:10]}-{d[3:5]}"
            else: # YYYY-MM-DD
                mes = d[0:7]
        else:
            mes = n.get('criado_em', '')[0:7]
            
        meses_dict[mes] = meses_dict.get(mes, {'mes': mes, 'total': 0, 'qtd_notas': 0})
        meses_dict[mes]['total'] += (n.get('valor_total') or 0)
        meses_dict[mes]['qtd_notas'] += 1
        
        # Mercado
        emit = n.get('emitente') or 'Desconhecido'
        mercados_dict[emit] = mercados_dict.get(emit, {'emitente': emit, 'total_gasto': 0, 'visitas': 0})
        mercados_dict[emit]['total_gasto'] += (n.get('valor_total') or 0)
        mercados_dict[emit]['visitas'] += 1
        
        # Produtos
        for p in n.get('produtos', []):
            nome = p.get('nome') or 'Produto'
            produtos_dict[nome] = produtos_dict.get(nome, {'nome': nome, 'vezes': 0, 'qtd_total': 0, 'total_pago': 0})
            produtos_dict[nome]['vezes'] += 1
            produtos_dict[nome]['qtd_total'] += float(p.get('qtd') or 1)
            produtos_dict[nome]['total_pago'] += float(p.get('valor_total') or 0)

    por_mes = sorted(list(meses_dict.values()), key=lambda x: x['mes'], reverse=True)[:12]
    top_mercados = sorted(list(mercados_dict.values()), key=lambda x: x['total_gasto'], reverse=True)[:10]
    
    top_produtos_lista = []
    for p in produtos_dict.values():
        p['preco_medio'] = p['total_pago'] / p['qtd_total'] if p['qtd_total'] else 0
        top_produtos_lista.append(p)
        
    top_produtos = sorted(top_produtos_lista, key=lambda x: x['vezes'], reverse=True)[:15]
    
    return jsonify({
        'resumo': {
            'total_notas': total_notas,
            'total_gasto': total_gasto,
            'ticket_medio': ticket_medio
        },
        'por_mes': por_mes,
        'top_mercados': top_mercados,
        'top_produtos': top_produtos
    })

# ─────────────── FRONTEND ───────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    porta = int(os.environ.get('PORT', 5000))
    print(f"[OK] Servidor SaaS Supabase rodando na porta {porta}")
    app.run(debug=True, port=porta, host='0.0.0.0')
