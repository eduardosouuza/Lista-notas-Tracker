"""
Script de teste do scraper - roda direto no terminal:
  python backend/test_scraper.py
"""
import sys, json, os
sys.path.insert(0, '.')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Força saida UTF-8 no Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from scraper import scrape_nota, parse_nota_do_html

# Chave real (CONSTANTINO BALDASSO - BUFFET LIVRE - R$ 39,50)
CHAVE = "43241204167842000193650010000686951002140520"

print("Buscando nota:", CHAVE)
print("-" * 60)

raw = scrape_nota(CHAVE)

print("Texto extraido (primeiros 1500 chars):")
print(raw.get("texto", "")[:1500])
print("\n" + "=" * 60)

nota = parse_nota_do_html(raw)

print("\nDados parseados:")
print(f"  Emitente    : {nota['emitente']}")
print(f"  CNPJ        : {nota['cnpj']}")
print(f"  Endereco    : {nota['endereco']}")
print(f"  Data Emissao: {nota['data_emissao']}")
print(f"  Numero      : {nota['numero']}")
print(f"  Valor Total : R$ {nota['valor_total']:.2f}")
print(f"  Produtos    : {len(nota['produtos'])} item(ns)")
for p in nota['produtos']:
    print(f"    - {p['nome']} | Qtd: {p['qtd']} | Unit: R$ {p['valor_unitario']:.2f} | Total: R$ {p['valor_total']:.2f}")

print("\nJSON completo:")
print(json.dumps(nota, ensure_ascii=False, indent=2))
