/* 专业英语课程知识库 · 前端 */
const API = '/api';

const S = {
  modules: [],
  stats: null,
  tab: 'papers',
  mod: '',
  q: '',
  subs: {},          // module -> 选中的子类
  askBusy: false,
  lastQuestion: '',
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`${res.status} ${txt.slice(0, 160)}`);
  }
  return res.json();
}

const modOf = id => S.modules.find(m => m.id === id) || { name: id, color: '#8A8171' };
const kindLabel = k => (k === 'paper' ? '文献' : '案例');

const L = { items: [], q: '', field: '', year: '', sort: 'cat' };
const LS = {
  status: cat => localStorage.getItem('lit:status:' + cat) || 'unread',
  setStatus: (cat, s) => localStorage.setItem('lit:status:' + cat, s),
  bookmarks: () => { try { return JSON.parse(localStorage.getItem('lit:bookmarks') || '[]'); } catch { return []; } },
  toggleBookmark: cat => {
    const b = LS.bookmarks();
    const on = !b.includes(cat);
    localStorage.setItem('lit:bookmarks', JSON.stringify(on ? [...b, cat] : b.filter(x => x !== cat)));
    return on;
  },
  note: cat => localStorage.getItem('lit:note:' + cat) || '',
  setNote: (cat, t) => localStorage.setItem('lit:note:' + cat, t),
};

const fmtSize = n => !n ? ''
  : n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB'
  : Math.max(1, Math.round(n / 1024)) + ' KB';

// 外部链接只显示短标签，完整地址放 title，避免长 URL 撑破元信息栏
const extLink = it => !it.url ? '无链接'
  : `<a href="${esc(it.url)}" target="_blank" rel="noopener" title="${esc(it.url)}">${it.linkKind === 'doi' ? 'DOI ↗' : '检索 ↗'}</a>`;

/* ---------------- 初始化 ---------------- */

async function init() {
  try {
    const [mods, stats] = await Promise.all([api('/modules'), api('/stats')]);
    S.modules = mods;
    S.stats = stats;
    renderRail();
    renderFacts();
  } catch (e) {
    $('#list').innerHTML = `<div class="answer-err">后端未启动或数据未导入：${esc(e.message)}</div>`;
    return;
  }
  bindTop();
  bindGlobal();
  bindPromptCopy();
  route();
}

function renderRail() {
  const isCases = S.tab === 'cases';
  const nav = $('#nav-modules');
  const total = S.modules.reduce((a, m) => a + (isCases ? m.caseCount : m.paperCount), 0);
  nav.innerHTML =
    `<a href="#/" data-mod="" class="${!S.mod ? 'is-active' : ''}" style="--c:#B9AF9C">
       <i></i><span>全部材料</span><em>${total}</em></a>` +
    S.modules.map(m => `
      <a href="#/m/${m.id}" data-mod="${m.id}" class="${S.mod === m.id ? 'is-active' : ''}" style="--c:${m.color}">
        <i></i><span>${esc(m.name)}</span><em>${isCases ? m.caseCount : m.paperCount}</em>
      </a>`).join('');

  $('#n-papers').textContent = S.stats ? S.stats.papers : '';
  $('#n-cases').textContent = S.stats ? S.stats.cases : '';
  $('#rail-foot').innerHTML = S.stats
    ? `${S.stats.papers} 篇文献 · ${S.stats.cases} 个案例<br>问答模型 ${esc(S.stats.model)}${S.stats.aiConfigured ? '' : '<br>未配置 API Key'}`
    : '';
  $('#foot-model').textContent = S.stats ? `Q&A · ${S.stats.model}` : '';
}

function renderFacts() {
  if (!S.stats) return;
  $('#facts').innerHTML = `
    <div><dt>PAPERS</dt><dd>${S.stats.papers}</dd></div>
    <div><dt>CASES</dt><dd>${S.stats.cases}</dd></div>
    <div><dt>MODULES</dt><dd>0${S.stats.modules}</dd></div>
    <div><dt>AI</dt><dd>${S.stats.aiConfigured ? 'READY' : 'NO KEY'}</dd></div>`;
}

function bindTop() {
  $$('.tabs button').forEach(btn => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });
  const input = $('#q');
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      S.q = input.value.trim();
      $('#clear').hidden = !input.value;
      if (location.hash.startsWith('#/ask')) location.hash = '#/';
      else if (!$('#view-home').hidden) renderHome();
      else location.hash = '#/';
    }, 220);
  });
  $('#clear').addEventListener('click', () => {
    input.value = '';
    S.q = '';
    $('#clear').hidden = true;
    renderHome();
    input.focus();
  });
  $('#search-form').addEventListener('submit', e => e.preventDefault());
}

function bindGlobal() {
  document.addEventListener('keydown', e => {
    if (e.key === '/' && !/input|textarea/i.test(document.activeElement.tagName)) {
      e.preventDefault();
      $('#q').focus();
    }
  });
  window.addEventListener('hashchange', route);
}

let promptCopyBound = false;
function bindPromptCopy() {
  if (promptCopyBound) return;
  const btn = $('#copy-prompt');
  if (!btn) return;
  promptCopyBound = true;
  btn.addEventListener('click', async () => {
    const base = $('#guide-prompt').textContent;
    const info = ($('#paper-input')?.value || '').trim();
    const text = info ? base + '\n\n' + info : base;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = info ? '已复制（含文献信息）' : '已复制';
    } catch {
      btn.textContent = '请手动选择复制';
    }
    setTimeout(() => { btn.textContent = '复制完整提示词'; }, 1800);
  });
}

function setTab(tab) {
  S.tab = tab;
  S.mod = '';
  $$('.tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  renderRail();
  if (location.hash && !location.hash.startsWith('#/m/') && location.hash !== '#/') {
    location.hash = '#/';
  } else {
    renderHome();
  }
}

/* ---------------- 路由 ---------------- */

function route() {
  const parts = location.hash.replace(/^#/, '').split('/').filter(Boolean);
  const showHome = () => {
    $('#view-home').hidden = false;
    $('#view-detail').hidden = true;
    $('#view-ask').hidden = true;
    $('#view-literature').hidden = true;
    $('#view-lit-detail').hidden = true;
    $('#view-prompt').hidden = true;
    $('#ask-link').classList.remove('is-active');
    $('#lit-link').classList.remove('is-active');
    $('#prompt-link').classList.remove('is-active');
  };

  if (parts[0] === 'prompt') {
    showPrompt();
    return;
  }
  if (parts[0] === 'ask') {
    showAsk();
    return;
  }
  if (parts[0] === 'paper' && parts[1]) {
    showDetail('paper', decodeURIComponent(parts[1]));
    return;
  }
  if (parts[0] === 'case' && parts[1]) {
    showDetail('case', decodeURIComponent(parts[1]));
    return;
  }
  if (parts[0] === 'literature') {
    showLiterature();
    return;
  }
  if (parts[0] === 'lit' && parts[1]) {
    showLitDetail(decodeURIComponent(parts[1]));
    return;
  }
  if (parts[0] === 'm' && parts[1]) S.mod = parts[1].toUpperCase();
  else S.mod = '';

  showHome();
  renderRail();
  setCrumb();
  renderHome();
}

function setCrumb() {
  const c = $('#crumb');
  if (!S.mod) {
    c.innerHTML = `<b>全部材料</b>`;
  } else {
    const m = modOf(S.mod);
    c.innerHTML = `<a href="#/">全部材料</a><span class="slash">/</span><b>${esc(m.name)}</b>`;
  }
}

/* ---------------- 首页列表 ---------------- */

async function renderHome() {
  const root = $('#list');
  const empty = $('#empty');
  root.innerHTML = '<div class="loading">LOADING</div>';
  empty.classList.remove('show');

  const isCases = S.tab === 'cases';
  const params = new URLSearchParams();
  if (S.mod) params.set('m', S.mod);
  if (S.q) params.set('q', S.q);
  const path = (isCases ? '/cases' : '/papers') + (params.toString() ? '?' + params : '');

  let items;
  try {
    items = await api(path);
  } catch (e) {
    root.innerHTML = `<div class="answer-err">载入失败：${esc(e.message)}</div>`;
    return;
  }
  if (S.mod && S.subs[S.mod]) {
    items = items.filter(x => x.sub === S.subs[S.mod]);
  }

  document.body.classList.toggle('is-filtered', !!(S.q || S.mod));
  const unit = isCases ? '个案例' : '篇文献';
  $('#result-count').textContent = S.q
    ? `「${S.q}」命中 ${items.length} ${unit}`
    : `${items.length} ${unit}`;

  if (!items.length) {
    root.innerHTML = '';
    empty.classList.add('show');
    return;
  }

  const mods = S.mod ? S.modules.filter(m => m.id === S.mod) : S.modules;
  root.innerHTML = mods.map(m => {
    const mine = items.filter(x => x.m === m.id);
    if (!mine.length) return '';
    return moduleHTML(m, mine, isCases);
  }).join('');

  bindModuleEvents(root);
}

function moduleHTML(m, items, isCases) {
  const subs = m.subs.map(sub => ({ sub, items: items.filter(x => x.sub === sub) }))
    .filter(g => g.items.length);

  const chips = subs.map(g => `
    <button class="chip ${S.subs[m.id] === g.sub ? 'is-active' : ''}" data-mod="${m.id}" data-sub="${esc(g.sub)}">
      ${esc(g.sub)}<span>${g.items.length}</span>
    </button>`).join('');

  const groups = subs.map(g => `
    <div class="subhead" id="sub-${CSS.escape(m.id + '-' + g.sub)}">
      <span>${esc(g.sub)}</span><em>${g.items.length}</em>
    </div>
    ${g.items.map(x => isCases ? caseHTML(x, m) : paperHTML(x, m)).join('')}`).join('');

  return `
    <section class="module" id="m-${m.id}" style="--mc:${m.color}">
      <div class="module-head">
        <div class="module-no">0${S.modules.findIndex(x => x.id === m.id) + 1}</div>
        <div>
          <p class="module-en">${esc(m.en)}</p>
          <h2>${esc(m.name)}</h2>
          <p class="module-desc">${esc(m.descr)}</p>
        </div>
        <div class="module-side">
          <div class="module-count"><strong>${items.length}</strong>${isCases ? '案例' : '文献'}</div>
        </div>
      </div>
      <div class="subs">${chips}</div>
      ${groups}
    </section>`;
}

function paperHTML(p, m) {
  const meta = [p.authors, p.venue, p.year, p.sub].filter(Boolean);
  const kw = (p.keywords || []).join(' · ');
  return `
    <article class="paper" data-kind="paper" data-id="${esc(p.id)}" style="--mc:${m.color}">
      <div class="paper-no">${esc(p.id)}</div>
      <div>
        <h3 class="paper-title">${esc(p.title)}</h3>
        ${p.cn ? `<p class="paper-cn">${esc(p.cn)}</p>` : ''}
        <p class="paper-meta">${meta.map(esc).join('<span class="dot">·</span>')}</p>
        ${kw ? `<p class="paper-kw">${esc(kw)}</p>` : ''}
      </div>
      <div class="paper-tail">
        <span class="paper-type">${esc(p.type || '')}</span>
        ${p.url && p.linkKind !== 'search' ? `<a class="paper-link" href="${esc(p.url)}" target="_blank" rel="noopener">原文 ↗</a>` : ''}
        ${p.hasPdf ? `<a class="paper-link" href="/api/papers/${encodeURIComponent(p.id)}/pdf" target="_blank" rel="noopener">PDF ↗</a>` : ''}
      </div>
    </article>`;
}

function caseHTML(c, m) {
  const meta = [c.author, c.source_topic, c.page ? `p.${c.page}` : ''].filter(Boolean);
  const tags = [c.sub, ...(c.tags || [])].filter(Boolean).join(' · ');
  return `
    <article class="paper is-case" data-kind="case" data-id="${esc(c.id)}" style="--mc:${m.color}">
      <div class="paper-no">${esc(c.id)}</div>
      <div>
        <h3 class="paper-title">${esc(c.title)}</h3>
        <p class="paper-meta">${meta.map(esc).join('<span class="dot">·</span>')}</p>
        <p class="paper-kw">${esc(tags)}</p>
      </div>
      <div class="paper-tail">
        <span class="paper-type">${c.char_count ? c.char_count + ' 字' : '案例'}</span>
        <span class="paper-link">阅读 →</span>
      </div>
    </article>`;
}

function bindModuleEvents(root) {
  $$('.paper', root).forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('a')) return;
      location.hash = `#/${el.dataset.kind}/${encodeURIComponent(el.dataset.id)}`;
    });
  });
  $$('.chip', root).forEach(el => {
    el.addEventListener('click', () => {
      const mod = el.dataset.mod;
      S.subs[mod] = S.subs[mod] === el.dataset.sub ? '' : el.dataset.sub;
      renderHome();
    });
  });
}

/* ---------------- 详情 ---------------- */

async function showDetail(kind, id) {
  $('#view-home').hidden = true;
  $('#view-ask').hidden = true;
  $('#view-literature').hidden = true;
  $('#view-lit-detail').hidden = true;
  $('#view-prompt').hidden = true;
  $('#ask-link').classList.remove('is-active');
  $('#lit-link').classList.remove('is-active');
  $('#prompt-link').classList.remove('is-active');
  const view = $('#view-detail');
  view.hidden = false;
  view.innerHTML = '<div class="loading">LOADING</div>';
  window.scrollTo({ top: 0 });

  let item, recs;
  try {
    [item, recs] = await Promise.all([
      api(`/${kind === 'paper' ? 'papers' : 'cases'}/${encodeURIComponent(id)}`),
      api(`/recommend/${encodeURIComponent(id)}`).catch(() => []),
    ]);
  } catch (e) {
    view.innerHTML = `<div class="detail"><a class="back" href="#/">← 返回</a>
      <div class="answer-err">读取失败：${esc(e.message)}</div></div>`;
    return;
  }

  const m = modOf(item.m);
  const isPaper = kind === 'paper';
  $('#crumb').innerHTML = `<a href="#/">全部材料</a><span class="slash">/</span>
    <a href="#/m/${m.id}">${esc(m.name)}</a><span class="slash">/</span><b>${esc(id)}</b>`;

  const heads = isPaper
    ? `<span class="tag solid">${m.id} · ${esc(m.name)}</span><span class="tag">${esc(item.sub || '')}</span><span class="tag">${esc(item.type || '')}</span>`
    : `<span class="tag solid">${m.id} · ${esc(m.name)}</span><span class="tag">${esc(item.sub || '')}</span>${item.source_topic ? `<span class="tag">原专题 · ${esc(item.source_topic)}</span>` : ''}`;

  let main;
  if (isPaper) {
    main = `
      <h1>${esc(item.title)}</h1>
      ${item.cn ? `<p class="cn-title">${esc(item.cn)}</p>` : ''}
      <dl class="detail-meta">
        <div><dt>编目号</dt><dd>${esc(item.id)}</dd></div>
        <div><dt>作者</dt><dd>${esc(item.authors || '未记录')}</dd></div>
        <div><dt>出处</dt><dd>${esc(item.venue || '未记录')}</dd></div>
        <div><dt>年份</dt><dd>${esc(item.year || '')}</dd></div>
        <div><dt>届别</dt><dd>${esc(item.archive || '')} 届</dd></div>
        <div><dt>类型</dt><dd>${esc(item.type || '')}</dd></div>
        <div><dt>原文</dt><dd>${item.url && item.linkKind !== 'search' ? extLink(item) : '无链接'}</dd></div>
        <div><dt>文件</dt><dd class="ellipsis" title="${esc(item.path || '')}">${esc(item.path || '')}</dd></div>
        ${item.hasPdf ? `<div><dt>PDF</dt><dd>${fmtSize(item.pdfSize)}</dd></div>` : ''}
      </dl>
      ${(item.keywords || []).length ? `<div class="kw-row">${item.keywords.map(k => `<span class="kw">${esc(k)}</span>`).join('')}</div>` : ''}
      ${item.hasPdf
        ? `<div class="pdf-view">
             <div class="pdf-bar">
               <span>PDF 原文 · ${fmtSize(item.pdfSize)}</span>
               <a href="/api/papers/${encodeURIComponent(item.id)}/pdf" target="_blank" rel="noopener">新窗口打开 ↗</a>
             </div>
             <div class="pdf-stage">
               <iframe class="pdf-native" src="/api/papers/${encodeURIComponent(item.id)}/pdf" title="PDF 原文"></iframe>
             </div>
           </div>`
        : `<div class="note-box">这篇没有可读的 PDF：原文件缺失、是扫描件，或未随服务部署。${item.url && item.linkKind !== 'search' ? '可以先点上方原文链接前往来源。' : ''}</div>`}`;
  } else {
    main = `
      <h1 class="case-h1">${esc(item.title)}</h1>
      <dl class="detail-meta">
        <div><dt>编号</dt><dd>${esc(item.id)}</dd></div>
        <div><dt>作者</dt><dd>${esc(item.author || '原文未署名')}</dd></div>
        <div><dt>原文页码</dt><dd>${item.page ? '第 ' + item.page + ' 页' : ''}</dd></div>
        <div><dt>字数</dt><dd>${item.char_count || 0}</dd></div>
      </dl>
      <div class="kw-row">${[item.sub, ...(item.tags || [])].filter(Boolean).map(k => `<span class="kw">${esc(k)}</span>`).join('')}</div>
      <div class="body-text">${(item.paragraphs || []).map(p => `<p>${esc(p)}</p>`).join('')}</div>`;
  }

  view.innerHTML = `
    <div class="detail" style="--mc:${m.color}">
      <a class="back" href="#/">← 返回列表</a>
      <div class="detail-grid">
        <div>
          <div class="detail-kicker">${heads}</div>
          ${main}
        </div>
        <aside>
          <p class="side-title">相关材料</p>
          <div class="rec-list">
            ${recs.length ? recs.map(r => `
              <a class="rec" href="#/${r.kind}/${encodeURIComponent(r.id)}">
                <span class="rec-id">${esc(r.id)} · ${kindLabel(r.kind)}</span>
                <p class="rec-title">${esc(r.title)}</p>
                <p class="rec-sub">${esc(r.sub || '')}</p>
              </a>`).join('') : '<p class="rec-sub">暂无相近条目</p>'}
          </div>
        </aside>
      </div>
    </div>`;
}

/* ---------------- 文献导读 ---------------- */

const STATUS_LABEL = { unread: '未读', reading: '在读', completed: '已读' };

const litBlock = (label, inner) => inner
  ? `<div class="lit-block"><h4>${label}</h4>${inner}</div>` : '';
const litP = (label, text) => litBlock(label, text ? `<p class="lit-text">${esc(text)}</p>` : '');
const litUL = (label, arr) => litBlock(label, arr && arr.length
  ? `<ul class="lit-list">${arr.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : '');
const litTags = (label, arr) => litBlock(label, arr && arr.length
  ? `<div class="kw-row">${arr.map(k => `<span class="kw">${esc(k)}</span>`).join('')}</div>` : '');

function litFlow(flow) {
  if (!flow || !flow.length) return '';
  return `<div class="lit-flow">${flow
    .map((s, i) => `<div class="lit-flow-step">${esc(s)}</div>${i < flow.length - 1 ? '<div class="lit-flow-arrow">↓</div>' : ''}`)
    .join('')}</div>`;
}

function litOverviewHTML(gu) {
  const ov = gu.overview || {};
  return [
    litP('研究动机', ov.research_motivation),
    litP('核心研究问题', ov.research_question),
    litUL('研究假设', ov.hypotheses),
    litUL('主要发现', ov.main_findings),
    litUL('学术贡献', ov.contributions),
    litTags('核心概念', gu.key_concepts),
    litUL('延伸阅读', gu.reading_recommendations),
  ].join('');
}

function litMechanismHTML(gu) {
  const me = gu.mechanism || {};
  return [
    litP('理论基础', me.theoretical_foundations),
    litUL('关键经济假设', me.key_assumptions),
    litUL('核心机制', me.mechanisms),
    litP('变量间关系', me.variable_relationships),
    litBlock('机制图示', litFlow(me.flow)),
  ].join('');
}

function litMethodsHTML(gu) {
  const mt = gu.methods || {};
  const kind = mt.paper_type === 'theoretical' ? '理论论文' : '实证论文';
  return [
    litBlock('论文类型', `<p class="lit-text"><span class="tag">${kind}</span></p>`),
    litP('数据来源', mt.data_sources),
    litP('样本区间', mt.sample_period),
    litUL('变量定义', mt.variables),
    litP('计量模型', mt.econometric_models),
    litP('识别策略', mt.identification_strategy),
    litP('内生性处理', mt.endogeneity_treatments),
    litP('稳健性检验', mt.robustness_checks),
    litUL('重要图表', mt.key_tables_figures),
  ].join('');
}

function litCritiqueHTML(gu) {
  const cr = gu.critique || {};
  return [
    litP('理论贡献', cr.theoretical_contributions),
    litP('方法优点', cr.methodological_strengths),
    litUL('研究局限', cr.limitations),
    litP('识别问题', cr.identification_problems),
    litP('替代解释', cr.alternative_explanations),
    litUL('未解问题', cr.unresolved_questions),
    litUL('后续方向', cr.follow_up_topics),
  ].join('');
}

function litTabsHTML(g) {
  const gu = g.guide || {};
  return `
    <div class="lit-tabs" id="lit-tabs">
      <div class="lit-tab-nav" role="tablist">
        <button role="tab" data-tab="overview" class="is-active">概览 <span>Overview</span></button>
        <button role="tab" data-tab="mechanism">机制 <span>Mechanism</span></button>
        <button role="tab" data-tab="methods">方法 <span>Methods</span></button>
        <button role="tab" data-tab="critique">评述 <span>Critique</span></button>
      </div>
      <div class="lit-tab-panel" data-panel="overview">${litOverviewHTML(gu)}</div>
      <div class="lit-tab-panel" data-panel="mechanism" hidden>${litMechanismHTML(gu)}</div>
      <div class="lit-tab-panel" data-panel="methods" hidden>${litMethodsHTML(gu)}</div>
      <div class="lit-tab-panel" data-panel="critique" hidden>${litCritiqueHTML(gu)}</div>
    </div>`;
}

async function showLiterature() {
  $('#view-home').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-ask').hidden = true;
  $('#view-lit-detail').hidden = true;
  $('#view-prompt').hidden = true;
  $('#ask-link').classList.remove('is-active');
  $('#prompt-link').classList.remove('is-active');
  $('#lit-link').classList.add('is-active');
  const view = $('#view-literature');
  view.hidden = false;
  $('#crumb').innerHTML = `<a href="#/">全部材料</a><span class="slash">/</span><b>文献导读</b>`;
  window.scrollTo({ top: 0 });

  if (!view.dataset.ready) {
    view.innerHTML = litHTML();
    bindLit();
    view.dataset.ready = '1';
  }
  if (!L.items.length) await loadLit();
  renderLitCards();
}

function litHTML() {
  return `
    <div class="lit-wrap">
      <div class="lit-head">
        <div>
          <p class="eyebrow">LITERATURE GUIDE · 100 PAPERS</p>
          <h1>文献导读</h1>
          <p class="lede">按主题发现文献，逐篇精读研究问题、机制、方法与评述。有导读的文献可进入四栏精读，其余可直接读原文。</p>
        </div>
        <div class="lit-count" id="lit-count"></div>
      </div>

      <div class="lit-filter">
        <div class="lit-search">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>
          <input id="lit-q" type="search" placeholder="搜索标题、作者、关键词、期刊…" aria-label="搜索文献">
        </div>
        <select id="lit-field" aria-label="研究领域"></select>
        <select id="lit-year" aria-label="年份"></select>
        <select id="lit-sort" aria-label="排序">
          <option value="cat">默认排序</option>
          <option value="year_desc">年份 新→旧</option>
          <option value="year_asc">年份 旧→新</option>
        </select>
      </div>

      <div class="lit-grid" id="lit-grid"></div>
      <div class="empty" id="lit-empty">
        <strong>没有匹配的文献</strong>
        <span>换个关键词或筛选条件。</span>
      </div>
    </div>`;
}

function bindLit() {
  const q = $('#lit-q');
  let t;
  q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { L.q = q.value.trim(); renderLitCards(); }, 180); });
  $('#lit-field').addEventListener('change', e => { L.field = e.target.value; renderLitCards(); });
  $('#lit-year').addEventListener('change', e => { L.year = e.target.value; renderLitCards(); });
  $('#lit-sort').addEventListener('change', e => { L.sort = e.target.value; renderLitCards(); });
}

async function loadLit() {
  try {
    L.items = await api('/literature');
  } catch (e) {
    $('#lit-grid').innerHTML = `<div class="answer-err">载入失败：${esc(e.message)}</div>`;
    return;
  }
  populateLitFilters();
}

function populateLitFilters() {
  const fields = new Set();
  (S.modules || []).forEach(m => (m.subs || []).forEach(s => fields.add(s)));
  $('#lit-field').innerHTML = `<option value="">全部领域</option>` +
    [...fields].sort().map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
  const years = [...new Set(L.items.map(i => i.year).filter(Boolean))].sort((a, b) => b - a);
  $('#lit-year').innerHTML = `<option value="">全部年份</option>` +
    years.map(y => `<option value="${y}">${y}</option>`).join('');
  $('#lit-field').value = L.field;
  $('#lit-year').value = L.year;
  $('#lit-sort').value = L.sort;
}

function renderLitCards() {
  const grid = $('#lit-grid');
  const empty = $('#lit-empty');
  let items = L.items.filter(it => {
    if (L.field && it.sub !== L.field) return false;
    if (L.year && String(it.year) !== L.year) return false;
    if (L.q) {
      const q = L.q.toLowerCase();
      const hay = [it.title, it.cn, it.authors, it.venue,
        (it.keywords || []).join(' '), it.sub, it.id].filter(Boolean).join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  if (L.sort === 'year_desc') items.sort((a, b) => (b.year || 0) - (a.year || 0) || (a.id < b.id ? -1 : 1));
  else if (L.sort === 'year_asc') items.sort((a, b) => (a.year || 0) - (b.year || 0) || (a.id < b.id ? -1 : 1));
  else items.sort((a, b) => (a.id < b.id ? -1 : 1));

  $('#lit-count').textContent = `${items.length} 篇 · 有导读 ${items.filter(i => i.hasGuide).length} 篇`;
  if (!items.length) {
    grid.innerHTML = '';
    empty.classList.add('show');
    return;
  }
  empty.classList.remove('show');
  grid.innerHTML = items.map(litCard).join('');
  bindLitCards(grid);
}

function litProvNote(g) {
  return `<p class="lit-prov-note">${g.generation ? '本导读由 AI 生成。' : '本导读为人工整理。'}</p>`;
}

function litCard(it) {
  const status = LS.status(it.id);
  const bookmarked = LS.bookmarks().includes(it.id);
  const kw = (it.keywords || []).slice(0, 5).join(' · ');
  return `
    <article class="lit-card" data-id="${esc(it.id)}">
      <div class="lit-card-top">
        <span class="lit-id">${esc(it.id)}</span>
        <span class="lit-status" data-status="${status}">${STATUS_LABEL[status] || '未读'}</span>
      </div>
      <h3 class="lit-title">${esc(it.title)}</h3>
      ${it.cn ? `<p class="lit-cn">${esc(it.cn)}</p>` : ''}
      <p class="lit-meta">${[it.authors, it.year, it.venue].filter(Boolean).map(esc).join(' · ')}</p>
      <p class="lit-field">${esc(it.sub || '')}</p>
      ${kw ? `<p class="lit-kw">${esc(kw)}</p>` : ''}
      <p class="lit-overview">${it.hasGuide ? esc(it.overview) : '导读尚未生成，可先阅读原文。'}</p>
      <div class="lit-card-foot">
        <button class="lit-bookmark ${bookmarked ? 'is-on' : ''}" data-act="bookmark">${bookmarked ? '★ 已收藏' : '☆ 收藏'}</button>
        ${it.hasGuide
          ? `<span class="lit-open">打开导读 →</span>`
          : (it.hasPdf ? `<a class="lit-open" href="/api/papers/${encodeURIComponent(it.id)}/pdf" target="_blank" rel="noopener">读原文 ↗</a>` : '')}
      </div>
    </article>`;
}

function bindLitCards(root) {
  $$('.lit-card', root).forEach(card => {
    card.addEventListener('click', e => {
      if (e.target.closest('[data-act]') || e.target.closest('a')) return;
      location.hash = `#/lit/${encodeURIComponent(card.dataset.id)}`;
    });
    const bm = $('[data-act="bookmark"]', card);
    if (bm) bm.addEventListener('click', e => {
      e.stopPropagation();
      const on = LS.toggleBookmark(card.dataset.id);
      bm.classList.toggle('is-on', on);
      bm.textContent = on ? '★ 已收藏' : '☆ 收藏';
    });
  });
}

async function showLitDetail(cat) {
  $('#view-home').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-ask').hidden = true;
  $('#view-literature').hidden = true;
  $('#view-prompt').hidden = true;
  $('#ask-link').classList.remove('is-active');
  $('#prompt-link').classList.remove('is-active');
  $('#lit-link').classList.add('is-active');
  const view = $('#view-lit-detail');
  view.hidden = false;
  view.innerHTML = '<div class="loading">LOADING</div>';
  window.scrollTo({ top: 0 });

  let item, recs;
  try {
    [item, recs] = await Promise.all([
      api(`/literature/${encodeURIComponent(cat)}`),
      api(`/recommend/${encodeURIComponent(cat)}`).catch(() => []),
    ]);
  } catch (e) {
    view.innerHTML = `<div class="detail"><a class="back" href="#/literature">← 返回导读</a>
      <div class="answer-err">读取失败：${esc(e.message)}</div></div>`;
    return;
  }

  const m = modOf(item.m);
  const g = item.guide;
  const bookmarked = LS.bookmarks().includes(cat);
  const status = LS.status(cat);
  $('#crumb').innerHTML = `<a href="#/literature">文献导读</a><span class="slash">/</span><b>${esc(cat)}</b>`;

  view.innerHTML = `
    <div class="lit-detail" style="--mc:${m.color}">
      <a class="back" href="#/literature">← 返回导读</a>

      <div class="detail-kicker">
        <span class="tag solid">${m.id} · ${esc(m.name)}</span>
        <span class="tag">${esc(item.sub || '')}</span>
        <span class="tag">${esc(item.type || '')}</span>
        ${g && g.generation && g.generation.completeness === 'partial' ? '<span class="tag tag-warn">资料不全</span>' : ''}
      </div>
      <h1>${esc(item.title)}</h1>
      ${item.cn ? `<p class="cn-title">${esc(item.cn)}</p>` : ''}
      <dl class="detail-meta">
        <div><dt>编目号</dt><dd>${esc(item.id)}</dd></div>
        <div><dt>作者</dt><dd>${esc(item.authors || '未记录')}</dd></div>
        <div><dt>出处</dt><dd>${esc(item.venue || '未记录')}</dd></div>
        <div><dt>年份</dt><dd>${esc(item.year || '')}</dd></div>
        <div><dt>届别</dt><dd>${esc(item.archive || '')} 届</dd></div>
        <div><dt>类型</dt><dd>${esc(item.type || '')}</dd></div>
        ${item.url ? `<div><dt>原文</dt><dd>${extLink(item)}</dd></div>` : ''}
        ${item.hasPdf ? `<div><dt>PDF</dt><dd><a href="/api/papers/${encodeURIComponent(item.id)}/pdf" target="_blank" rel="noopener">阅读原文 ↗</a></dd></div>` : ''}
      </dl>
      ${(item.keywords || []).length ? `<div class="kw-row">${item.keywords.map(k => `<span class="kw">${esc(k)}</span>`).join('')}</div>` : ''}

      <div class="lit-tools">
        <div class="lit-tool">
          <span class="lit-tool-label">阅读状态</span>
          <div class="lit-status-switch">
            ${['unread', 'reading', 'completed'].map(s =>
              `<button data-status="${s}" class="${status === s ? 'is-on' : ''}">${STATUS_LABEL[s]}</button>`).join('')}
          </div>
        </div>
        <button class="lit-bookmark ${bookmarked ? 'is-on' : ''}" id="lit-detail-bookmark">${bookmarked ? '★ 已收藏' : '☆ 收藏'}</button>
      </div>

      ${g ? litProvNote(g) + litTabsHTML(g) : `<div class="note-box">这篇文献的导读尚未生成。可读上方 PDF 原文，也可先收藏、标记阅读状态、写笔记。</div>`}

      <div class="lit-notes">
        <p class="lit-tool-label">阅读笔记（保存在本机浏览器）</p>
        <textarea id="lit-note" placeholder="记录想法、疑问、待查文献…">${esc(LS.note(cat))}</textarea>
      </div>

      <aside class="lit-rec">
        <p class="side-title">相关材料</p>
        <div class="rec-list">
          ${recs.length ? recs.map(r => `
            <a class="rec" href="#/${r.kind}/${encodeURIComponent(r.id)}">
              <span class="rec-id">${esc(r.id)} · ${kindLabel(r.kind)}</span>
              <p class="rec-title">${esc(r.title)}</p>
              <p class="rec-sub">${esc(r.sub || '')}</p>
            </a>`).join('') : '<p class="rec-sub">暂无相近条目</p>'}
        </div>
      </aside>
    </div>`;

  bindLitDetail(cat);
}

function bindLitDetail(cat) {
  const tabs = $('#lit-tabs');
  if (tabs) tabs.addEventListener('click', e => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;
    $$('[data-tab]', tabs).forEach(b => b.classList.toggle('is-active', b === btn));
    $$('[data-panel]', tabs).forEach(p => { p.hidden = (p.dataset.panel !== btn.dataset.tab); });
  });

  $$('.lit-status-switch button').forEach(b => {
    b.addEventListener('click', () => {
      LS.setStatus(cat, b.dataset.status);
      $$('.lit-status-switch button').forEach(x => x.classList.toggle('is-on', x === b));
    });
  });

  const bm = $('#lit-detail-bookmark');
  if (bm) bm.addEventListener('click', () => {
    const on = LS.toggleBookmark(cat);
    bm.classList.toggle('is-on', on);
    bm.textContent = on ? '★ 已收藏' : '☆ 收藏';
  });

  const note = $('#lit-note');
  if (note) {
    let t;
    note.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => LS.setNote(cat, note.value), 300); });
  }
}

/* ---------------- 问答 ---------------- */

function showPrompt() {
  $('#view-home').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-ask').hidden = true;
  $('#view-literature').hidden = true;
  $('#view-lit-detail').hidden = true;
  $('#view-prompt').hidden = false;
  $('#ask-link').classList.remove('is-active');
  $('#lit-link').classList.remove('is-active');
  $('#prompt-link').classList.add('is-active');
  $('#crumb').innerHTML = `<a href="#/">全部材料</a><span class="slash">/</span><b>导读提示词</b>`;
  window.scrollTo({ top: 0 });
  bindPromptCopy();
}

function showAsk() {
  $('#view-home').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-literature').hidden = true;
  $('#view-lit-detail').hidden = true;
  $('#view-prompt').hidden = true;
  $('#ask-link').classList.add('is-active');
  $('#lit-link').classList.remove('is-active');
  $('#prompt-link').classList.remove('is-active');
  const view = $('#view-ask');
  view.hidden = false;
  $('#ask-link').classList.add('is-active');
  $('#lit-link').classList.remove('is-active');
  $('#crumb').innerHTML = `<a href="#/">全部材料</a><span class="slash">/</span><b>库内问答</b>`;
  window.scrollTo({ top: 0 });

  if (!view.dataset.ready) {
    view.innerHTML = askHTML();
    bindAsk();
    view.dataset.ready = '1';
  }
  setTimeout(() => $('#ask-input').focus(), 60);
}

function askHTML() {
  const s = S.stats || {};
  const ready = !!s.aiConfigured;
  return `
    <div class="ask-wrap">
      <div class="ask-head">
        <div>
          <p class="eyebrow">RETRIEVAL-AUGMENTED · 带出处</p>
          <h1>库内问答</h1>
          <p>先在本库检索，再把命中的材料交给模型作答。每条结论后标出来源编号，点编号跳到对应条目。答不出就说没有，不编。</p>
        </div>
        <div class="ask-badge">
          <b>${s.cases ?? 44}</b> 篇案例全文可读<br>
          ${s.papers ?? 100} 篇文献仅题录<br>
          ${esc(s.model || 'deepseek-chat')}
        </div>
      </div>

      ${ready ? '' : '<p class="ask-warn">服务端还没配置模型 key，问答暂不可用。浏览、检索与相关推荐不受影响。</p>'}

      <form class="ask-form" id="ask-form">
        <textarea class="ask-input" id="ask-input" maxlength="4000" ${ready ? '' : 'disabled'}
          placeholder="例如：宽带中国战略的实施效果如何？也可以把「导读 prompt」整段粘进来，生成某篇文献的阅读卡片。"></textarea>
        <div class="ask-actions">
          <span class="ask-hint">Enter 提交 · Shift + Enter 换行 · 最多 4000 字</span>
          <button class="ask-submit" type="submit" id="ask-submit" ${ready ? '' : 'disabled'}>提问</button>
        </div>
      </form>

      <div class="examples" id="examples" ${ready ? '' : 'data-off'}>
        <button>宽带中国战略的实施效果如何？</button>
        <button>哪些案例讨论了税收激励与财政竞争？</button>
        <button>关于区域经济趋同，库中有哪些材料？</button>
        <button>比较深圳经济特区与波兰经济特区的做法</button>
        <button>田纳西流域开发的经验是什么？</button>
      </div>

      <section class="answer" id="answer">
        <div class="answer-head"><span>ANSWER</span><span id="answer-state"></span></div>
        <div class="answer-text" id="answer-text"></div>
        <div id="answer-err"></div>
        <div class="sources" id="sources" hidden>
          <h3 id="sources-title">检索到的材料</h3>
          <div class="source-list" id="source-list"></div>
        </div>
      </section>

      <p class="ask-note">AI 可能出错。引用前请点开来源核对原文；文献条目只有题录，不包含论文观点与数据。</p>
    </div>`;
}

function bindAsk() {
  const form = $('#ask-form');
  const input = $('#ask-input');
  form.addEventListener('submit', e => {
    e.preventDefault();
    submitAsk(input.value.trim());
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitAsk(input.value.trim());
    }
  });
  $('#examples').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b || !S.stats?.aiConfigured) return;
    input.value = b.textContent;
    submitAsk(b.textContent);
  });
  $('#answer-text').addEventListener('click', e => {
    const c = e.target.closest('.cite');
    if (!c) return;
    const card = $(`.source-card[data-n="${c.dataset.n}"]`);
    if (!card) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.classList.add('is-flash');
    setTimeout(() => card.classList.remove('is-flash'), 1400);
  });
  $('#source-list').addEventListener('click', e => {
    const card = e.target.closest('.source-card');
    if (!card) return;
    location.hash = `#/${card.dataset.kind}/${encodeURIComponent(card.dataset.id)}`;
  });
}

async function submitAsk(question) {
  if (!question || S.askBusy) return;
  S.askBusy = true;
  S.lastQuestion = question;
  $('#ask-submit').disabled = true;
  $('#ask-submit').textContent = '检索中…';

  const answer = $('#answer');
  const text = $('#answer-text');
  const err = $('#answer-err');
  const sources = $('#sources');
  answer.classList.add('show');
  text.innerHTML = '';
  err.innerHTML = '';
  sources.hidden = true;
  $('#answer-state').textContent = '正在检索库内材料';
  let scrolled = false;

  let acc = '';
  let streamDone = false;
  let empty = false;
  let failed = false;

  try {
    const res = await fetch(`${API}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!res.ok || !res.body) {
      let msg = `服务端返回 ${res.status}`;
      try {
        const j = await res.json();
        if (j.detail) msg = j.detail;
      } catch { /* 非 JSON 错误体，保留状态码 */ }
      throw new Error(msg);
    }
    $('#ask-submit').textContent = '生成中…';
    $('#answer-state').textContent = '生成中';

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (!streamDone) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const ev = parseSSE(chunk);
        if (!ev) continue;
        if (ev.event === 'sources') {
          renderSources(ev.data.sources || []);
        } else if (ev.event === 'delta') {
          if (!scrolled) {
            scrolled = true;
            const top = answer.getBoundingClientRect().top + window.scrollY - 88;
            window.scrollTo({ top, behavior: 'smooth' });
          }
          acc += ev.data.text || '';
          paintAnswer(text, acc, true);
        } else if (ev.event === 'error') {
          failed = true;
          err.innerHTML = `<div class="answer-err">${esc(ev.data.message || '调用失败')}</div>`;
          streamDone = true;
        } else if (ev.event === 'done') {
          if (ev.data && ev.data.empty) {
            empty = true;
            acc = ev.data.answer || '库中没有找到相关材料。';
          }
          streamDone = true;
        }
      }
    }
    paintAnswer(text, acc, false);
    $('#answer-state').textContent = failed ? '调用失败'
      : empty ? '库中无相关材料'
      : (acc ? '依据库内材料生成' : '无回答');
  } catch (e) {
    err.innerHTML = `<div class="answer-err">请求失败：${esc(e.message)}</div>`;
    $('#answer-state').textContent = '失败';
  } finally {
    S.askBusy = false;
    $('#ask-submit').disabled = false;
    $('#ask-submit').textContent = '提问';
  }
}

function parseSSE(chunk) {
  let event = 'message';
  const dataLines = [];
  for (const line of chunk.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) };
  } catch {
    return null;
  }
}

function paintAnswer(el, content, streaming) {
  const html = esc(content).replace(/\[(\d{1,2})\]/g,
    (_, n) => `<button class="cite" data-n="${n}" title="跳到来源 ${n}">${n}</button>`);
  el.innerHTML = html + (streaming ? '<span class="cursor"></span>' : '');
}

function renderSources(list) {
  if (!list.length) return;
  $('#sources-title').textContent = `检索到的材料 · ${list.length} 条`;
  $('#source-list').innerHTML = list.map((s, i) => `
    <article class="source-card" data-n="${i + 1}" data-id="${esc(s.id)}" data-kind="${esc(s.kind)}">
      <div class="source-n">${i + 1}</div>
      <div>
        <div class="source-id">${esc(s.id)} · ${kindLabel(s.kind)} · 模块 ${esc(s.module)}${s.sub ? ' · ' + esc(s.sub) : ''}</div>
        <p class="source-title">${esc(s.title)}</p>
        <p class="source-snip">${esc(s.snippet || '')}</p>
      </div>
    </article>`).join('');
  $('#sources').hidden = false;
}

init();
