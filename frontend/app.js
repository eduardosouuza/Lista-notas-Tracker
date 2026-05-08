const API = window.location.hostname === 'localhost' ? 'http://localhost:5000/api' : '/api';
const SUPABASE_URL = 'https://lbiaiuvikvyjoegbvemr.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxiaWFpdXZpa3Z5am9lZ2J2ZW1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNTE4NzUsImV4cCI6MjA5MzcyNzg3NX0.LwllAh9OXe00uuDFXv4Sr98RZrBIZ50EN9-_uVWy-bA';

// Usa var para permitir redeclaração se o live reload rodar o script novamente sem erro
var sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
var sessionToken = null;

let chartMensal   = null;
let chartMercados = null;

// ─── AUTHENTICATION ───

function showAuthPage(mode) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${mode}`).classList.add('active');
  document.getElementById('login-status').style.display = 'none';
  document.getElementById('reg-status').style.display = 'none';
}

async function handleLogin() {
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  const statusEl = document.getElementById('login-status');
  
  if (!email || !password) {
    setStatusEl(statusEl, 'Preencha todos os campos.', 'error');
    return;
  }
  
  setStatusEl(statusEl, 'Entrando...', 'loading');

  try {
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw error;
  } catch (error) {
    setStatusEl(statusEl, error.message.includes('Invalid login') ? 'E-mail ou senha incorretos.' : error.message, 'error');
  }
}

async function handleRegister() {
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;
  const statusEl = document.getElementById('reg-status');
  
  if (!email || !password) {
    setStatusEl(statusEl, 'Preencha todos os campos.', 'error');
    return;
  }
  
  setStatusEl(statusEl, 'Criando conta...', 'loading');

  try {
    const { data, error } = await sb.auth.signUp({ email, password });
    if (error) throw error;
    
    if (data.user && !data.session) {
      setStatusEl(statusEl, 'Conta criada! Confirme seu e-mail para entrar.', 'success');
    } else if (data.session) {
      setStatusEl(statusEl, 'Conta criada! Entrando...', 'success');
    }
  } catch (error) {
    setStatusEl(statusEl, error.message, 'error');
  }
}

function setStatusEl(el, text, type) {
  el.textContent = text;
  el.className = `status-msg ${type}`;
  el.style.display = 'block';
}

async function handleLogout() {
  await sb.auth.signOut();
}

async function checkSession() {
  // Listener para mudanças de estado
  sb.auth.onAuthStateChange((event, session) => {
    console.log('Auth event:', event, !!session);
    updateSessionState(session);
  });

  // Checagem inicial
  const { data: { session } } = await sb.auth.getSession();
  updateSessionState(session);
}

function updateSessionState(session) {
  console.log('Updating session state:', !!session);
  const nav = document.getElementById('nav-menu');
  
  if (session) {
    sessionToken = session.access_token;
    nav.style.display = 'flex';
    
    const activePage = document.querySelector('.page.active')?.id;
    if (activePage === 'page-login' || activePage === 'page-register' || !activePage) {
      showPage('dashboard');
    }
  } else {
    sessionToken = null;
    nav.style.display = 'none';
    
    const activePage = document.querySelector('.page.active')?.id;
    if (activePage !== 'page-login' && activePage !== 'page-register') {
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.getElementById('page-login').classList.add('active');
    }
  }
}

async function fetchAPI(endpoint, options = {}) {
  if (!options.headers) options.headers = {};
  if (sessionToken) options.headers['Authorization'] = `Bearer ${sessionToken}`;
  
  const res = await fetch(`${API}${endpoint}`, options);
  if (res.status === 401) {
    handleLogout();
  }
  return res;
}

function showPage(name) {
  if (!sessionToken && name !== 'login' && name !== 'register') {
    showAuthPage('login');
    return;
  }

  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  
  const targetPage = document.getElementById(`page-${name}`);
  if (targetPage) targetPage.classList.add('active');
  
  const btns = document.querySelectorAll('.nav-btn:not(.nav-btn-danger)');
  const idx = { dashboard: 0, notas: 1, buscar: 2 };
  if (btns[idx[name]]) btns[idx[name]].classList.add('active');

  if (name === 'dashboard') carregarDashboard();
  if (name === 'notas')     carregarNotas();
}

function fmt(val) {
  return `R$ ${parseFloat(val || 0).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`;
}
function fmtMes(mes) {
  if (!mes) return '—';
  const [y, m] = mes.split('-');
  const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  return `${meses[parseInt(m)-1]}/${y.slice(2)}`;
}

async function carregarDashboard() {
  try {
    const data = await fetchAPI('/dashboard').then(r => r.json());
    const r = data.resumo;

    document.getElementById('c-total').textContent   = fmt(r.total_gasto);
    document.getElementById('c-notas').textContent   = `${r.total_notas || 0} nota(s) cadastrada(s)`;
    document.getElementById('c-ticket').textContent  = fmt(r.ticket_medio);
    document.getElementById('c-mercados').textContent = data.top_mercados.length;

    const meses  = [...data.por_mes].reverse();
    const labels = meses.map(m => fmtMes(m.mes));
    const totais = meses.map(m => parseFloat(m.total || 0));

    if (chartMensal) chartMensal.destroy();
    chartMensal = new Chart(document.getElementById('chart-mensal'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Gasto (R$)',
          data: totais,
          backgroundColor: 'rgba(16, 185, 129, 0.5)',
          hoverBackgroundColor: 'rgba(16, 185, 129, 0.8)',
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#a1a1aa', font: { family: 'Inter', size: 12 } } },
          y: {
            grid: { color: '#27272a', drawBorder: false }, ticks: {
              color: '#a1a1aa', font: { family: 'Inter', size: 12 },
              callback: v => `R$ ${v}`
            },
            border: { display: false }
          }
        }
      }
    });

    const topM = data.top_mercados.slice(0, 6);
    if (chartMercados) chartMercados.destroy();
    chartMercados = new Chart(document.getElementById('chart-mercados'), {
      type: 'doughnut',
      data: {
        labels: topM.map(m => m.emitente?.substring(0, 18) || '?'),
        datasets: [{
          data: topM.map(m => parseFloat(m.total_gasto || 0)),
          backgroundColor: ['#10b981','#3b82f6','#8b5cf6','#f59e0b','#ef4444','#06b6d4'],
          borderColor: '#121214',
          borderWidth: 4,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#a1a1aa', font: { family: 'Inter', size: 11 }, boxWidth: 10, padding: 16 }
          }
        },
        cutout: '70%',
      }
    });

    const tbody = document.getElementById('tabela-produtos');
    if (!data.top_produtos.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">Sem dados ainda</td></tr>`;
    } else {
      tbody.innerHTML = data.top_produtos.slice(0, 10).map((p, i) => `
        <tr>
          <td class="td-muted">${String(i+1).padStart(2,'0')}</td>
          <td>${p.nome}</td>
          <td><span class="badge">${p.vezes}x</span></td>
          <td style="font-family:var(--font-mono)">${fmt(p.preco_medio)}</td>
          <td class="td-muted">${parseFloat(p.qtd_total||0).toFixed(2)}</td>
        </tr>
      `).join('');
    }
  } catch(e) {
    console.error('Erro dashboard:', e);
  }
}

function fmtDataEmissao(dataStr) {
  if (!dataStr) return '—';
  if (/^\d{2}\/\d{2}\/\d{4}/.test(dataStr)) return dataStr.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}/.test(dataStr)) {
    const [y, m, d] = dataStr.slice(0, 10).split('-');
    return `${d}/${m}/${y}`;
  }
  return dataStr.slice(0, 10);
}

function notaParaChaveMes(nota) {
  const d = nota.data_emissao || '';
  if (/^\d{2}\/\d{2}\/\d{4}/.test(d)) {
    const [dia, mes, ano] = d.split('/');
    return `${ano}-${mes}`;
  }
  if (/^\d{4}-\d{2}/.test(d)) return d.slice(0, 7);
  const c = nota.criado_em || '';
  return c.slice(0, 7) || '0000-00';
}

function fmtChaveMesLabel(chave) {
  if (!chave || chave === '0000-00') return 'Sem data';
  const [ano, mes] = chave.split('-');
  const meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
  return `${meses[parseInt(mes, 10) - 1]} ${ano}`;
}

async function carregarNotas() {
  const lista = document.getElementById('lista-notas');
  try {
    const notas = await fetchAPI('/notas').then(r => r.json());
    document.getElementById('total-notas-label').textContent = `${notas.length} nota(s)`;

    if (!notas.length) {
      lista.innerHTML = `<div class="empty-state"><div class="icon">🧾</div><h3>Nenhuma nota ainda</h3><p>Adicione sua primeira nota pela aba "+ Adicionar"</p></div>`;
      return;
    }

    notas.sort((a, b) => notaParaChaveMes(b).localeCompare(notaParaChaveMes(a)));

    const grupos = {};
    const ordem = [];
    notas.forEach(n => {
      const chave = notaParaChaveMes(n);
      if (!grupos[chave]) { grupos[chave] = []; ordem.push(chave); }
      grupos[chave].push(n);
    });

    let html = '';
    let numGlobal = 0;
    ordem.forEach(chave => {
      const grupo = grupos[chave];
      const totalMes = grupo.reduce((s, n) => s + parseFloat(n.valor_total || 0), 0);
      html += `<div class="mes-separator"><div class="mes-label"><span class="mes-nome">${fmtChaveMesLabel(chave)}</span><span class="mes-count">${grupo.length} nota(s)</span></div><div class="mes-total">${fmt(totalMes)}</div></div>`;
      grupo.forEach(n => {
        numGlobal++;
        html += `<div class="nota-item" onclick="abrirNota(${n.id})"><div class="nota-num">${String(numGlobal).padStart(2,'0')}</div><div class="nota-info"><div class="nota-nome">${n.emitente || 'Estabelecimento'}</div><div class="nota-meta">${fmtDataEmissao(n.data_emissao) || n.criado_em?.slice(0,10) || '—'} · ${n.total_itens || 0} iten(s) ${n.numero ? `· Nº ${n.numero}` : ''}</div></div><div class="nota-valor">${fmt(n.valor_total)}</div><button class="nota-delete" onclick="deletarNota(event, ${n.id})" title="Remover"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button></div>`;
      });
    });
    lista.innerHTML = html;
  } catch(e) {
    lista.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Erro ao carregar</h3><p>Verifique se o servidor está rodando</p></div>`;
  }
}

async function deletarNota(e, id) {
  e.stopPropagation();
  if (!confirm('Remover esta nota?')) return;
  await fetchAPI(`/notas/${id}`, { method: 'DELETE' });
  carregarNotas();
}

async function abrirNota(id) {
  try {
    const nota = await fetchAPI(`/notas/${id}`).then(r => r.json());
    document.getElementById('modal-emitente').textContent = nota.emitente || 'Estabelecimento';
    document.getElementById('modal-meta').textContent = `${nota.data_emissao || '—'} · Chave: ${nota.chave?.slice(0,20)}...`;
    document.getElementById('modal-total').textContent = fmt(nota.valor_total);
    const tbody = document.getElementById('modal-produtos');
    if (!nota.produtos?.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:24px">Produtos não extraídos</td></tr>`;
    } else {
      tbody.innerHTML = nota.produtos.map(p => `<tr><td>${p.nome}</td><td class="td-num">${parseFloat(p.qtd||1).toFixed(3)}</td><td class="td-num">${fmt(p.valor_unitario)}</td><td class="td-total">${fmt(p.valor_total)}</td></tr>`).join('');
    }
    document.getElementById('modal-overlay').classList.add('open');
  } catch(e) { alert('Erro ao abrir nota'); }
}

function fecharModal(e) {
  if (!e || e.target === document.getElementById('modal-overlay') || !e.target) {
    document.getElementById('modal-overlay').classList.remove('open');
  }
}

async function buscarNota() {
  const chave = document.getElementById('input-chave').value.trim();
  const btn   = document.getElementById('btn-buscar');
  if (!chave) { setStatus('Informe a chave ou URL da nota.', 'error'); return; }
  btn.disabled = true;
  document.getElementById('status-msg').style.display = 'none';
  document.getElementById('search-group').style.display = 'none';
  document.getElementById('btn-scan-qr').style.display = 'none';
  const skeleton = document.getElementById('skeleton-loading');
  const skeletonText = document.getElementById('skeleton-status-text');
  skeleton.style.display = 'block';
  skeletonText.textContent = 'Conectando à SEFAZ-RS...';
  let steps = 0;
  const interval = setInterval(() => {
    steps++;
    if (steps === 1) skeletonText.textContent = 'Baixando dados do DANFE...';
    if (steps === 2) skeletonText.textContent = 'Extraindo produtos...';
  }, 4000);
  try {
    const res = await fetchAPI('/buscar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chave }) });
    const data = await res.json();
    if (res.status === 409) { setStatus(`⚠️ Nota já cadastrada.`, 'error'); return; }
    if (!res.ok) { setStatus(`❌ ${data.erro || 'Erro desconhecido'}`, 'error'); return; }
    setStatus(`✅ Nota adicionada! ${data.emitente || ''}`, 'success');
    document.getElementById('input-chave').value = '';
  } catch(e) {
    setStatus('❌ Erro de conexão.', 'error');
  } finally {
    clearInterval(interval);
    skeleton.style.display = 'none';
    document.getElementById('search-group').style.display = 'flex';
    document.getElementById('btn-scan-qr').style.display = 'flex';
    btn.disabled = false;
  }
}

let html5QrcodeScanner = null;
function startQRScanner() {
  const reader = document.getElementById('reader');
  const btnScan = document.getElementById('btn-scan-qr');
  reader.style.display = 'block'; btnScan.style.display = 'none';
  document.getElementById('search-group').style.display = 'none';
  if (!html5QrcodeScanner) {
    html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: {width: 250, height: 250} }, false);
  }
  html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}
function onScanSuccess(decodedText) {
  html5QrcodeScanner.clear().then(() => {
    document.getElementById('reader').style.display = 'none';
    document.getElementById('btn-scan-qr').style.display = 'flex';
    document.getElementById('search-group').style.display = 'flex';
    document.getElementById('input-chave').value = decodedText;
    buscarNota();
  });
}
function onScanFailure(error) {}
function setStatus(texto, tipo) {
  const el = document.getElementById('status-msg');
  el.textContent = texto; el.className = `status-msg ${tipo}`; el.style.display = 'block';
}
document.getElementById('input-chave')?.addEventListener('keydown', e => { if (e.key === 'Enter') buscarNota(); });

checkSession();
