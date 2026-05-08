import re

import requests
from bs4 import BeautifulSoup

SEFAZ_URL = "https://www.sefaz.rs.gov.br/NFE/NFE-NFC.aspx"
SEFAZ_IFRAME_URL = "https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_1.asp"
SEFAZ_POST_URL = "https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def limpar_chave(entrada: str) -> str:
    """Extrai a chave de 44 digitos de uma URL ou string."""
    match = re.search(r'[?&](?:chNFe|p|chaveNFe)=([0-9]{44})', entrada)
    if match:
        return match.group(1)
    apenas_numeros = re.sub(r'\D', '', entrada)
    if len(apenas_numeros) >= 44:
        return apenas_numeros[:44]
    raise ValueError(f"Chave invalida. Esperado 44 digitos, recebido: {len(apenas_numeros)}")


def scrape_nota(chave: str) -> dict:
    """Busca a NFC-e na SEFAZ-RS sem depender de navegador/Chromium."""
    chave = limpar_chave(chave)
    url = f"{SEFAZ_URL}?chaveNFe={chave}"

    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": USER_AGENT})
            session.get(SEFAZ_IFRAME_URL, params={"chaveNFe": chave}, timeout=20)
            response = session.post(
                SEFAZ_POST_URL,
                data={"HML": "false", "chaveNFe": chave, "Action": "Avancar"},
                headers={"Referer": url},
                timeout=30,
            )
            response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Erro ao buscar nota na SEFAZ: {e}") from e

    response.encoding = response.apparent_encoding or "iso-8859-1"
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text("\n", strip=True)

    if re.search(r'erro|inv[aá]lida|n[aã]o encontrada', texto, re.IGNORECASE):
        raise RuntimeError("A SEFAZ nao retornou uma NFC-e valida para esta chave")

    return {
        "chave": chave,
        "url": url,
        "texto": texto,
        "html": html,
        "produtos_js": _extrair_produtos_html(soup),
    }


def _extrair_produtos_html(soup: BeautifulSoup) -> list[dict]:
    for table in soup.find_all("table"):
        cells = [cell.get_text(" ", strip=True) for cell in table.find_all(["th", "td"])]
        normalized = [re.sub(r"\s+", " ", cell).strip() for cell in cells if cell.strip()]
        lowered = [cell.lower() for cell in normalized]

        headers = ["código", "descrição", "qtde", "un", "vl unit", "vl total"]
        if lowered[:6] != headers:
            continue

        produtos = []
        for i in range(6, len(normalized), 6):
            row = normalized[i:i + 6]
            if len(row) < 6:
                continue
            codigo, nome, qtd, un, v_unit, v_total = row
            if not codigo or not nome:
                continue
            produtos.append({
                "nome": nome,
                "qtd": qtd,
                "un": un,
                "vUnit": v_unit,
                "vTotal": v_total,
            })
        return produtos

    return []


def _re(padrao, texto, grupo=1, flags=re.IGNORECASE | re.MULTILINE):
    m = re.search(padrao, texto, flags)
    return m.group(grupo).strip() if m else None


def parse_nota_do_html(dados_raw: dict) -> dict:
    """Extrai estrutura limpa a partir do texto/HTML retornado pela SEFAZ."""
    texto = dados_raw.get("texto", "")
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]

    def parse_valor(v):
        if not v:
            return 0.0
        v = re.sub(r'[^\d,.]', '', str(v))
        if ',' in v and '.' in v:
            v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            v = v.replace(',', '.')
        try:
            return float(v)
        except Exception:
            return 0.0

    emitente = None
    for i, linha in enumerate(linhas):
        if re.search(r'CONSULTA DA NFC', linha, re.IGNORECASE):
            for candidato in linhas[i + 1:i + 6]:
                if candidato and not re.search(
                    r'NFC|DANFE|NFe|Consulta|Voltar|Imprimir|Enviar',
                    candidato,
                    re.IGNORECASE,
                ):
                    emitente = candidato
                    break
            break

    if not emitente:
        for i, linha in enumerate(linhas):
            if 'CNPJ' in linha.upper() and i > 0:
                emitente = linhas[i - 1]
                break

    cnpj = _re(r'CNPJ[:\s\n]+([0-9]{2}\.?[0-9]{3}\.?[0-9]{3}\/?[0-9]{4}-?[0-9]{2})', texto)

    endereco = None
    for i, linha in enumerate(linhas):
        if cnpj and cnpj in linha:
            for candidato in linhas[i + 1:i + 6]:
                if candidato and not re.search(r'DANFE|NFC|Emiss', candidato, re.IGNORECASE):
                    endereco = candidato
                    break
            break

    data_emissao = _re(r'Data de Emiss[aã]o[:\s\n]+([0-9]{2}/[0-9]{2}/[0-9]{4})', texto)

    numero = _re(r'NFC-e\s+n[º°o\.]+[:\s\n]*([0-9]+)', texto)
    if not numero:
        numero = _re(r'NFC-e\s+n\s*[:\s\n]*([0-9]+)', texto)

    total_str = _re(r'Valor total\s+R\$\s*\n?\s*([\d\.,]+)', texto)
    if not total_str:
        total_str = _re(r'VALOR PAGO\s*R\$\s*\n?\s*[\w\s]*\n?\s*([\d\.,]+)', texto)
    valor_total = parse_valor(total_str)

    produtos = []
    for p in dados_raw.get("produtos_js", []):
        nome = (p.get("nome") or "").strip()
        if nome and len(nome) > 1:
            produtos.append({
                "nome": nome,
                "qtd": parse_valor(p.get("qtd")),
                "valor_unitario": parse_valor(p.get("vUnit")),
                "valor_total": parse_valor(p.get("vTotal")),
            })

    if not produtos:
        for i, linha in enumerate(linhas):
            if linha.lower() == "código" and linhas[i + 1:i + 6] == ["Descrição", "Qtde", "Un", "Vl Unit", "Vl Total"]:
                j = i + 6
                while j + 5 < len(linhas) and not re.search(r'valor total|forma pag|desconto', linhas[j], re.IGNORECASE):
                    produtos.append({
                        "nome": linhas[j + 1],
                        "qtd": parse_valor(linhas[j + 2]),
                        "valor_unitario": parse_valor(linhas[j + 4]),
                        "valor_total": parse_valor(linhas[j + 5]),
                    })
                    j += 6
                break

    return {
        "chave": dados_raw.get("chave"),
        "emitente": emitente or "Desconhecido",
        "cnpj": cnpj,
        "endereco": endereco,
        "data_emissao": data_emissao,
        "numero": numero,
        "valor_total": valor_total,
        "produtos": produtos,
        "url": dados_raw.get("url"),
    }
