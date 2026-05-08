import urllib.request, urllib.error, json, sys

CHAVE = "43241204167842000193650010000686951002140520"

print(f"Buscando nota via API: {CHAVE}")
print("-" * 60)

body = json.dumps({"chave": CHAVE}).encode()
req = urllib.request.Request(
    'http://localhost:5000/api/buscar',
    data=body,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=60) as r:
        nota = json.loads(r.read())
        print("SUCESSO!")
        print(f"  Emitente  : {nota.get('emitente')}")
        print(f"  CNPJ      : {nota.get('cnpj')}")
        print(f"  Data      : {nota.get('data_emissao')}")
        print(f"  Total     : R$ {nota.get('valor_total')}")
        print(f"  Produtos  : {len(nota.get('produtos', []))} item(ns)")
        for p in nota.get('produtos', []):
            print(f"    - {p['nome']} | {p['qtd']}x | R$ {p['valor_total']}")
except urllib.error.HTTPError as e:
    print(f"ERRO HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"ERRO: {e}")
