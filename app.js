const state = { data: null, group: 'all', search: '', loading: false };
const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const clockFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const safeUrl = (value) => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } };

function icon(source) {
  const wrapper = document.createElement('span');
  wrapper.className = 'site-icon';
  wrapper.setAttribute('aria-hidden', 'true');
  wrapper.textContent = source.name.charAt(0);
  const image = document.createElement('img');
  image.src = source.icon || `icons/${source.id}.png`;
  image.alt = '';
  image.loading = 'lazy';
  image.addEventListener('error', () => image.remove(), { once: true });
  wrapper.append(image);
  return wrapper;
}

function relativeTime(date) {
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return 'à l’instant';
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h`;
}

function renderSources(sources, articles) {
  const list = byId('sources-list');
  list.replaceChildren();
  for (const source of sources) {
    const row = document.createElement('a');
    row.className = 'source-row';
    row.href = safeUrl(source.url) || '#';
    row.target = '_blank';
    row.rel = 'noopener noreferrer';
    row.append(icon(source));
    const description = document.createElement('span');
    description.className = 'source-description';
    description.textContent = source.name;
    const group = document.createElement('small');
    group.textContent = source.group;
    description.append(group);
    row.append(description);
    const status = document.createElement('span');
    status.className = `source-status${source.ok ? '' : ' failed'}`;
    const count = articles.filter((article) => article.source === source.id).length;
    status.textContent = source.ok ? (count ? `${count} article${count > 1 ? 's' : ''}` : 'Aucune nouveauté') : 'Collecte indisponible';
    if (!source.ok) status.title = source.error || 'Réessai à la prochaine collecte';
    row.append(status);
    list.append(row);
  }
}

function render() {
  if (!state.data) return;
  const now = Date.now();
  const cutoff = now - 48 * 3600000;
  const sources = new Map(state.data.sources.map((source) => [source.id, source]));
  const articles = state.data.articles.filter((article) => {
    const timestamp = Date.parse(article.publishedAt);
    return sources.has(article.source) && safeUrl(article.url) && timestamp >= cutoff && timestamp <= now;
  }).sort((first, second) => Date.parse(second.publishedAt) - Date.parse(first.publishedAt));
  const filtered = articles.filter((article) => {
    const source = sources.get(article.source);
    return (state.group === 'all' || source.group === state.group) && normalize(`${article.title} ${source.name}`).includes(state.search);
  });
  byId('today').textContent = dateFormat.format(new Date()).toUpperCase();
  byId('total-count').textContent = articles.length;
  byId('result-count').textContent = `${filtered.length} article${filtered.length > 1 ? 's' : ''} sur 48 heures`;
  byId('source-count').textContent = sources.size;
  byId('footer-sources').textContent = `${sources.size} sources`;
  const generated = new Date(state.data.generatedAt);
  byId('updated').replaceChildren();
  const dot = document.createElement('span');
  dot.className = 'status-dot';
  byId('updated').append(dot, `Collecte ${relativeTime(generated)}`);
  byId('updated').title = `Dernière collecte : ${generated.toLocaleString('fr-FR')}. Actualisation planifiée environ toutes les 15 minutes.`;
  const failed = state.data.sources.filter((source) => !source.ok).length;
  const stale = now - generated.getTime() > 3600000;
  byId('notice').hidden = !failed && !stale;
  byId('notice').textContent = [stale ? 'La collecte a du retard. Les articles de plus de 48 heures sont automatiquement masqués.' : '', failed ? `${failed} source${failed > 1 ? 's' : ''} temporairement indisponible${failed > 1 ? 's' : ''}. Détails dans « Les sources » ; les articles déjà collectés sont conservés pendant 48 heures.` : ''].filter(Boolean).join(' ');
  const feed = byId('feed');
  feed.replaceChildren();
  const days = new Map();
  for (const article of filtered) {
    const date = new Date(article.publishedAt);
    const day = date.toLocaleDateString('fr-FR');
    if (!days.has(day)) days.set(day, { date, articles: [] });
    days.get(day).articles.push(article);
  }
  const today = new Date().toLocaleDateString('fr-FR');
  const yesterdayDate = new Date();
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterday = yesterdayDate.toLocaleDateString('fr-FR');
  for (const [day, collection] of days) {
    const section = document.createElement('section');
    section.className = 'day-section';
    const heading = document.createElement('h2');
    heading.className = 'day-heading';
    heading.textContent = day === today ? 'Aujourd’hui' : day === yesterday ? 'Hier' : dateFormat.format(collection.date);
    const count = document.createElement('span');
    count.textContent = ` / ${collection.articles.length}`;
    heading.append(count);
    section.append(heading);
    const list = document.createElement('div');
    list.className = 'article-list';
    for (const article of collection.articles) {
      const source = sources.get(article.source);
      const date = new Date(article.publishedAt);
      const link = document.createElement('a');
      link.className = 'article';
      link.href = safeUrl(article.url);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.title = `${source.name} · ${date.toLocaleString('fr-FR')} · Nouvel onglet`;
      link.append(icon(source));
      const content = document.createElement('div');
      content.className = 'article-content';
      const title = document.createElement('span');
      title.className = 'article-title';
      title.textContent = article.title;
      const label = document.createElement('span');
      label.className = 'article-source';
      label.textContent = source.name;
      content.append(title, label);
      const time = document.createElement('time');
      time.className = 'article-time';
      time.dateTime = article.publishedAt;
      time.textContent = clockFormat.format(date);
      const arrow = document.createElement('span');
      arrow.className = 'article-arrow';
      arrow.textContent = '↗';
      arrow.setAttribute('aria-hidden', 'true');
      link.append(content, time, arrow);
      list.append(link);
    }
    section.append(list);
    feed.append(section);
  }
  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = state.search ? 'Aucun article ne correspond à votre recherche.' : 'Aucune nouveauté dans les dernières 48 heures. Revenez un peu plus tard.';
    feed.append(empty);
  }
  renderSources(state.data.sources, articles);
}

async function load() {
  if (state.loading) return;
  state.loading = true;
  byId('refresh').disabled = true;
  byId('feed').setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(`data/articles.json?t=${Date.now()}`, { cache: 'no-store', signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.articles) || !Array.isArray(data.sources) || !Number.isFinite(Date.parse(data.generatedAt))) throw new Error('Données invalides');
    state.data = data;
    render();
  } catch {
    byId('notice').hidden = false;
    byId('notice').textContent = 'Impossible de charger les actualités. Vérifiez votre connexion et réessayez avec le bouton d’actualisation.';
    if (!state.data) { byId('feed').textContent = ''; byId('result-count').textContent = 'Fil indisponible'; byId('updated').textContent = 'Connexion interrompue'; }
  } finally {
    state.loading = false;
    byId('refresh').disabled = false;
    byId('feed').setAttribute('aria-busy', 'false');
  }
}

document.querySelectorAll('[data-group]').forEach((button) => button.addEventListener('click', () => {
  state.group = button.dataset.group;
  document.querySelectorAll('[data-group]').forEach((tab) => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); });
  render();
}));
byId('search').addEventListener('input', (event) => { state.search = normalize(event.target.value.trim()); render(); });
byId('refresh').addEventListener('click', load);
byId('show-sources').addEventListener('click', () => byId('sources-dialog').showModal());
byId('close-sources').addEventListener('click', () => byId('sources-dialog').close());
byId('sources-dialog').addEventListener('click', (event) => { if (event.target === byId('sources-dialog')) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
setInterval(render, 60000);
setInterval(() => { if (!document.hidden) load(); }, 300000);
load();
