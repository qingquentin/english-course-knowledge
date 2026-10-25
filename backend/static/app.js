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

function setTab(tab) {
  S.tab = tab;
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
    $('#ask-link').classList.remove('is-active');
  };

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
        ${p.url ? `<a class="paper-link" href="${esc(p.url)}" target="_blank" rel="noopener">${p.linkKind === 'search' ? '检索 ↗' : '原文 ↗'}</a>` : ''}
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
  $('#ask-link').classList.remove('is-active');
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
        <div><dt>原文</dt><dd>${item.url ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.url)}</a>` : '无链接'}</dd></div>
        <div><dt>文件</dt><dd>${esc(item.path || '')}</dd></div>
      </dl>
      ${(item.keywords || []).length ? `<div class="kw-row">${item.keywords.map(k => `<span class="kw">${esc(k)}</span>`).join('')}</div>` : ''}
      <div class="note-box">本库中该文献只收题录（标题、作者、出处、DOI 或检索链接），正文未入库。问答涉及这篇时只会复述题录，不会推测论文内容。</div>`;
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

/* ---------------- 问答 ---------------- */

function showAsk() {
  $('#view-home').hidden = true;
  $('#view-detail').hidden = true;
  const view = $('#view-ask');
  view.hidden = false;
  $('#ask-link').classList.add('is-active');
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
        <textarea class="ask-input" id="ask-input" maxlength="500" ${ready ? '' : 'disabled'}
          placeholder="例如：宽带中国战略的实施效果如何？库中哪些案例讨论了税收激励与财政竞争？"></textarea>
        <div class="ask-actions">
          <span class="ask-hint">Enter 提交 · Shift + Enter 换行</span>
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
