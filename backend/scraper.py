from playwright.sync_api import sync_playwright
import re

SEFAZ_URL = "https://www.sefaz.rs.gov.br/NFE/NFE-NFC.aspx"


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
    """
    Faz scraping da NFC-e na SEFAZ-RS.

    Fluxo da pagina:
      1. A URL principal carrega um iframe (frames[1]) com o formulario.
      2. O iframe ja vem com chaveNFe preenchida via querystring.
      3. Clicamos no botao submit 'Avançar' dentro do iframe.
      4. Apos o submit, o iframe exibe o DANFE NFC-e renderizado via XSLT.
      5. Extraimos dados via innerText (com tabs entre celulas de tabela).
    """
    chave = limpar_chave(chave)
    url = f"{SEFAZ_URL}?chaveNFe={chave}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
        except Exception as e:
            browser.close()
            raise RuntimeError(f"Erro ao carregar a pagina da SEFAZ: {e}")

        # A pagina principal e frames[0]; o iframe do formulario e frames[1]
        if len(page.frames) < 2:
            browser.close()
            raise RuntimeError("Iframe da SEFAZ nao encontrado (frames < 2)")

        iframe = page.frames[1]

        btn = iframe.query_selector('input[type=submit]')
        if not btn:
            browser.close()
            raise RuntimeError("Botao 'Avançar' nao encontrado no iframe")

        btn.click()
        page.wait_for_timeout(4000)

        # Texto puro (o innerText preserva \t entre celulas de tabela)
        texto = iframe.inner_text('body')

        # Extrai produtos a partir do innerText tab-separado
        # Cabecalho: "Codigo\tDescricao\tQtde\tUn\tVl Unit\tVl Total"
        # Produto:   "1\tBUFFET LIVRE\t1\tUN\t39,5\t39,50"
        produtos_js = iframe.evaluate("""() => {
            const texto = document.body ? document.body.innerText : '';
            const linhas = texto.split('\\n').map(l => l.trim()).filter(l => l);

            let produtos = [];
            let dentroTabela = false;

            for (const linha of linhas) {
                const partes = linha.split('\\t').map(p => p.trim());
                const txt = partes.join('|').toLowerCase();

                // Detecta linha de cabecalho da tabela de produtos
                if (txt.includes('descri') && (txt.includes('qtd') || txt.includes('vl unit'))) {
                    dentroTabela = true;
                    continue;
                }

                // Para ao encontrar a secao de totais
                if (dentroTabela && /valor total|forma pag|desconto/i.test(linha)) {
                    break;
                }

                // Linha de produto valida: pelo menos 4 colunas tab-separadas
                if (dentroTabela && partes.length >= 4) {
                    // Estrutura: [codigo, nome, qtd, un, vUnit, vTotal]
                    const nome = partes[1] || partes[0];
                    if (nome && nome.length > 1 && !/valor|forma|desconto|pagamento/i.test(nome)) {
                        produtos.push({
                            nome:   nome,
                            qtd:    partes[2] || '',
                            un:     partes[3] || '',
                            vUnit:  partes[4] || '',
                            vTotal: partes[5] || partes[4] || '',
                        });
                    }
                }
            }
            return produtos;
        }""")

        browser.close()

    return {
        "chave": chave,
        "url": url,
        "texto": texto,
        "produtos_js": produtos_js,
    }


# ─── Helpers ───────────────────────────────────────────────────────────────

def _re(padrao, texto, grupo=1, flags=re.IGNORECASE | re.MULTILINE):
    m = re.search(padrao, texto, flags)
    return m.group(grupo).strip() if m else None


def parse_nota_do_html(dados_raw: dict) -> dict:
    """
    Extrai estrutura limpa a partir do texto puro do DANFE NFC-e.

    Exemplo do texto retornado pelo iframe apos o submit:

        CONSULTA DA NFC-e
        CONSTANTINO BALDASSO
        CNPJ: 04.167.842/0001-93 Inscricao Estadual: 0962847143
        RUA DOS ANDRADAS, 1358, CENTRO, PORTO ALEGRE, RS
        DANFE NFC-e - ...
        NFC-e no: 68695 Serie: 1 Data de Emissao: 20/12/2024 11:34:07
        ...
        Codigo  Descricao  Qtde  Un  Vl Unit  Vl Total
        1       BUFFET LIVRE  1  UN  39,5  39,50
        Valor total R$  39,50
    """
    texto = dados_raw.get("texto", "")
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]

    def parse_valor(v):
        if not v:
            return 0.0
        v = re.sub(r'[^\d,.]', '', str(v))
        if ',' in v and '.' in v:
            # Formato BR: 1.234,56 -> 1234.56
            v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            # Formato: 39,50 -> 39.50
            v = v.replace(',', '.')
        try:
            return float(v)
        except Exception:
            return 0.0

    # ── Emitente ─────────────────────────────────────────────────────────
    # Aparece como a primeira linha significativa apos "CONSULTA DA NFC-e"
    emitente = None
    for i, linha in enumerate(linhas):
        if re.search(r'CONSULTA DA NFC', linha, re.IGNORECASE):
            for j in range(i + 1, min(i + 6, len(linhas))):
                candidato = linhas[j]
                if (candidato and len(candidato) > 2
                        and not re.search(
                            r'NFC|DANFE|NFe|Consulta|Voltar|Imprimir|Enviar',
                            candidato, re.IGNORECASE
                        )):
                    emitente = candidato
                    break
            break

    # Fallback: linha imediatamente antes do CNPJ
    if not emitente:
        for i, linha in enumerate(linhas):
            if 'CNPJ' in linha.upper() and i > 0:
                candidato = linhas[i - 1]
                if candidato and len(candidato) > 2 and not re.search(
                    r'NFC|DANFE|Consulta|Voltar|Imprimir', candidato, re.IGNORECASE
                ):
                    emitente = candidato
                break

    # ── CNPJ ─────────────────────────────────────────────────────────────
    cnpj = _re(r'CNPJ[:\s]+([0-9]{2}\.?[0-9]{3}\.?[0-9]{3}\/?[0-9]{4}-?[0-9]{2})', texto)

    # ── Endereço ─────────────────────────────────────────────────────────
    endereco = None
    m_cnpj_pos = re.search(r'CNPJ[^\n]+', texto, re.IGNORECASE)
    if m_cnpj_pos:
        resto = texto[m_cnpj_pos.end():].lstrip()
        primeira = resto.splitlines()[0].strip() if resto else None
        if primeira and len(primeira) > 5:
            endereco = primeira

    # ── Data de emissão ───────────────────────────────────────────────────
    data_emissao = _re(r'Data de Emiss[aã]o[:\s]+([0-9]{2}/[0-9]{2}/[0-9]{4})', texto)

    # ── Número da nota ────────────────────────────────────────────────────
    numero = _re(r'NFC-e\s+n[º°o\.]+[:\s]*([0-9]+)', texto)
    if not numero:
        numero = _re(r'NFC-e\s+n\s*[:\s]*([0-9]+)', texto)

    # ── Valor total ───────────────────────────────────────────────────────
    total_str = _re(r'Valor total\s+R\$\s*([\d\.,]+)', texto)
    if not total_str:
        total_str = _re(r'VALOR PAGO\s*R\$\s*([\d\.,]+)', texto)
    valor_total = parse_valor(total_str)

    # ── Produtos ──────────────────────────────────────────────────────────
    produtos = []

    # 1) Via extração JS do innerText tab-separado (principal)
    for p in dados_raw.get("produtos_js", []):
        nome = (p.get("nome") or "").strip()
        if nome and len(nome) > 1:
            produtos.append({
                "nome": nome,
                "qtd": parse_valor(p.get("qtd")),
                "valor_unitario": parse_valor(p.get("vUnit")),
                "valor_total": parse_valor(p.get("vTotal")),
            })

    # 2) Fallback: extrai via regex no texto puro com tabs
    if not produtos:
        in_produtos = False
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            partes = [p.strip() for p in linha.split('\t')]

            txt = '|'.join(partes).lower()
            if 'descri' in txt and ('qtd' in txt or 'vl unit' in txt):
                in_produtos = True
                continue
            if in_produtos and re.search(r'valor total|forma pag|desconto', linha, re.IGNORECASE):
                break
            if in_produtos and len(partes) >= 4:
                nome = partes[1] if len(partes) > 1 else partes[0]
                if nome and not re.search(r'Valor|Forma|Desconto|Pago', nome, re.IGNORECASE):
                    produtos.append({
                        "nome": nome,
                        "qtd": parse_valor(partes[2] if len(partes) > 2 else ''),
                        "valor_unitario": parse_valor(partes[4] if len(partes) > 4 else ''),
                        "valor_total": parse_valor(partes[5] if len(partes) > 5 else ''),
                    })

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
