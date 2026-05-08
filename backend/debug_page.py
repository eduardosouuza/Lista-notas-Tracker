import sys
sys.path.insert(0, '.')
from playwright.sync_api import sync_playwright

chave = '43241204167842000193650010000686951002140520'
url = f'https://www.sefaz.rs.gov.br/NFE/NFE-NFC.aspx?chaveNFe={chave}'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
    )
    page = context.new_page()
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(2500)
    
    iframe = page.frames[1]
    btn = iframe.query_selector('input[type=submit]')
    btn.click()
    page.wait_for_timeout(4000)
    
    # Inspeciona todas as tabelas
    tabelas_info = iframe.evaluate("""() => {
        return [...document.querySelectorAll('table')].map((t, i) => {
            const rows = [...t.querySelectorAll('tr')].map(tr => 
                [...tr.querySelectorAll('td, th')].map(c => c.innerText.trim().substring(0, 60)).join(' | ')
            );
            return { index: i, id: t.id, className: t.className, rows: rows.slice(0, 8) };
        });
    }""")
    
    for t in tabelas_info:
        print(f"TABELA {t['index']} - id={t['id']} class={t['className']}")
        for r in t['rows']:
            print(f"  {r}")
        print()
    
    browser.close()
