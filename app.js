const state = { data: null, mangas: null, mangaError: false, mangaLoading: false, group: 'Tech', loading: false };
const renderCache = { sources: null, mangas: null, feed: null };
const versions = { news: 0, mangas: 0 };
const tabs = [...document.querySelectorAll('[data-group]')];
const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const clockFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const safeUrl = (value) => { try { const url = new URL(value); return typeof value === 'string' && ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; } catch { return null; } };

function validSource(source) {
  return source && typeof source.id === 'string' && /^[a-z0-9-]+$/.test(source.id) && typeof source.name === 'string' && ['BD', 'Sport', 'Tech'].includes(source.group) && !!safeUrl(source.url);
}
function validArticle(article) {
  return article && typeof article.source === 'string' && typeof article.title === 'string' && !!safeUrl(article.url) && Number.isFinite(Date.parse(article.publishedAt));
}
function validManga(manga) {
  return manga && typeof manga.title === 'string' && !!(safeUrl(manga.url) || safeUrl(manga.pageUrl));
}

function mangaDate(manga) {
  const value = manga.publishedDate;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return null;
  const date = new Date(`${value}T12:00:00`);
  if (!Number.isFinite(date.getTime()) || date.getFullYear() !== Number(value.slice(0, 4)) || date.getMonth() + 1 !== Number(value.slice(5, 7)) || date.getDate() !== Number(value.slice(8, 10))) return null;
  const observed = new Date(manga.firstSeenAt || manga.lastSuccessAt);
  // Une date sans fuseau fournie par la source peut devancer un chapitre déjà disponible.
  if (Number.isFinite(observed.getTime()) && observed.getTime() <= Date.now()) {
    const observedDay = new Date(observed.getFullYear(), observed.getMonth(), observed.getDate(), 12);
    if (date > observedDay) return { date: observedDay, observed: true };
  }
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  return date <= today ? { date, observed: false } : null;
}

function icon(source) {
  const wrapper = document.createElement('span');
  wrapper.className = 'site-icon';
  wrapper.setAttribute('aria-hidden', 'true');
  wrapper.textContent = source.name.charAt(0);
  const image = document.createElement('img');
  const path = source.icon || `icons/${source.id}.png`;
  if (!/^icons\/[a-z0-9-]+\.(png|jpg)$/.test(path)) return wrapper;
  image.src = path;
  image.width = image.height = 18;
  image.decoding = 'async';
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
  if (!byId('sources-dialog').open) return;
  const key = `${versions.news}:${articles.length}`;
  if (renderCache.sources === key) return;
  renderCache.sources = key;
  const counts = new Map();
  for (const article of articles) counts.set(article.source, (counts.get(article.source) || 0) + 1);
  const list = document.createDocumentFragment();
  for (const source of sources) {
    const row = element('a', 'source-row');
    row.href = safeUrl(source.url);
    row.target = '_blank';
    row.rel = 'noopener noreferrer';
    const description = element('span', 'source-description', source.name);
    description.append(element('small', '', `${source.group} · ${source.language === 'en' ? 'Anglais' : 'Français'}`));
    const count = counts.get(source.id) || 0;
    const status = element('span', `source-status${source.ok ? '' : ' failed'}`, source.ok ? (count ? `${count} article${count > 1 ? 's' : ''}` : 'Aucune nouveauté') : 'Collecte indisponible');
    if (!source.ok) status.title = source.error || 'Réessai à la prochaine collecte';
    row.append(icon(source), description, status);
    list.append(row);
  }
  byId('sources-list').replaceChildren(list);
}

function renderMangas() {
  const section = byId('manga-feed');
  section.hidden = state.group !== 'BD';
  if (section.hidden) return;
  const key = `${versions.mangas}:${state.mangaError}`;
  if (renderCache.mangas === key) {
    section.hidden = !section.childElementCount;
    return;
  }
  renderCache.mangas = key;
  section.replaceChildren();
  if (!state.mangas) {
    section.append(element('p', 'manga-info', state.mangaError ? 'Impossible de charger les mangas. Réessayez en rechargeant la page.' : 'Chargement des derniers chapitres…'));
  } else if (state.mangaError || state.mangas.some((manga) => !manga.ok)) {
    section.append(element('p', 'notice', 'Certaines vérifications sont indisponibles. Les derniers chapitres connus restent affichés.'));
  }
  section.hidden = !section.childElementCount;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function articleLink(entry, sources) {
  const manga = entry.manga;
  const article = manga || entry.article;
  const source = manga ? { id: manga.source === 'otl' ? 'otl' : 'mangakatana', name: manga.source === 'otl' ? 'OTL' : 'MangaKatana' } : sources.get(article.source);
  const link = element('a', manga ? 'article manga-article' : 'article');
  link.href = safeUrl(article.url) || safeUrl(article.pageUrl);
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  const label = source.name + (manga && !manga.ok ? ' · à vérifier' : '');
  const displayed = manga ? mangaDate(manga) : null;
  const time = element(manga ? 'span' : 'time', 'article-time', manga ? (displayed ? `${displayed.observed ? 'Repéré le ' : ''}${displayed.date.toLocaleDateString('fr-FR')}` : 'Date inconnue') : clockFormat.format(entry.date));
  if (!manga) time.dateTime = article.publishedAt;
  if (displayed?.observed) time.title = `Date annoncée par ${source.name} : ${manga.publishedDate}. Chapitre déjà disponible lors de la collecte.`;
  link.title = manga ? (manga.lastSuccessAt ? `Dernière vérification réussie : ${new Date(manga.lastSuccessAt).toLocaleString('fr-FR')}` : 'Chapitre non vérifié') : `${source.name} · ${entry.date.toLocaleString('fr-FR')} · Nouvel onglet`;
  const metadata = element('div', 'article-metadata');
  metadata.append(icon(source), element('span', 'article-source', label), time);
  link.append(metadata, element('span', 'article-title', manga ? `${manga.title} — ${manga.chapter || 'Chapitre indisponible'}` : article.title));
  return link;
}

async function fetchData(path) {
  const response = await fetch(`data/${path}.json`, { cache: 'no-cache', signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

// Les dates de mangas ne comportent pas d’heure : elles restent au jour local.
function feedEntries(articles, mangas) {
  return [
    ...articles.map((article) => ({ article, date: new Date(article.publishedAt) })),
    ...mangas.map((manga) => ({ manga, date: mangaDate(manga)?.date || null })),
  ].sort((first, second) => (second.date?.getTime() ?? -Infinity) - (first.date?.getTime() ?? -Infinity));
}

async function loadMangas() {
  if (state.mangaLoading) return;
  state.mangaLoading = true;
  try {
    const data = await fetchData('mangas');
    if (!Array.isArray(data.mangas)) throw new Error('Données invalides');
    if (!data.mangas.every(validManga)) throw new Error('Données invalides');
    if (JSON.stringify(state.mangas) !== JSON.stringify(data.mangas)) versions.mangas++;
    state.mangas = data.mangas;
    state.mangaError = false;
  } catch {
    state.mangaError = true;
  } finally {
    state.mangaLoading = false;
    render();
  }
}

function render() {
  renderMangas();
  if (!state.data) return;
  const now = Date.now();
  const cutoff = now - 48 * 3600000;
  const sources = new Map(state.data.sources.map((source) => [source.id, source]));
  const articles = state.data.articles.filter((article) => {
    const timestamp = Date.parse(article.publishedAt);
    return sources.has(article.source) && safeUrl(article.url) && (timestamp >= cutoff || sources.get(article.source).group === 'BD') && timestamp <= now;
  }).sort((first, second) => Date.parse(second.publishedAt) - Date.parse(first.publishedAt));
  const today = new Date(now).toLocaleDateString('fr-FR');
  const counts = { BD: 0, Sport: 0, Tech: 0 };
  for (const article of articles) {
    const source = sources.get(article.source);
    if (new Date(article.publishedAt).toLocaleDateString('fr-FR') === today && Object.hasOwn(counts, source.group)) {
      counts[source.group] += 1;
    }
  }
  // Les chapitres du jour contribuent au compteur BD.
  for (const manga of state.mangas || []) {
    if (mangaDate(manga)?.date.toLocaleDateString('fr-FR') === today && safeUrl(manga.url)) counts.BD += 1;
  }
  tabs.forEach((button) => {
    const group = button.dataset.group;
    button.querySelector('.tab-count').textContent = counts[group];
    button.setAttribute('aria-label', `${group} : ${counts[group]} publication${counts[group] === 1 ? '' : 's'} aujourd’hui`);
  });
  const filtered = articles.filter((article) => {
    const source = sources.get(article.source);
    return source.group === state.group;
  });
  byId('source-count').textContent = sources.size;
  const generated = new Date(state.data.generatedAt);
  byId('updated-time').textContent = relativeTime(generated);
  byId('updated').setAttribute('aria-label', `Dernière collecte : ${relativeTime(generated)}`);
  byId('updated').title = `Dernière collecte : ${generated.toLocaleString('fr-FR')}. Collecte programmée toutes les 15 minutes, sous réserve des délais de GitHub.`;
  const failed = state.data.sources.filter((source) => !source.ok).length;
  const stale = now - generated.getTime() > 3600000;
  byId('notice').hidden = !failed && !stale;
  byId('notice').textContent = [stale ? 'La collecte a du retard. Les actualités de plus de 48 heures sont masquées, sauf les dernières publications BD.' : '', failed ? `${failed} source${failed > 1 ? 's' : ''} temporairement indisponible${failed > 1 ? 's' : ''}. Détails dans « Sources » ; les articles sont conservés pendant 48 heures, sans expiration pour la dernière publication BD.` : ''].filter(Boolean).join(' ');
  renderSources(state.data.sources, articles);
  const mangas = state.group === 'BD' ? state.mangas || [] : [];
  const feedKey = `${versions.news}:${versions.mangas}:${state.group}:${today}:${filtered.length}`;
  if (renderCache.feed === feedKey) return;
  renderCache.feed = feedKey;
  const entries = feedEntries(filtered, mangas);
  const feed = byId('feed');
  const fragment = document.createDocumentFragment();
  const days = new Map();
  for (const entry of entries) {
    const date = entry.date;
    const day = date ? date.toLocaleDateString('fr-FR') : 'Date inconnue';
    if (!days.has(day)) days.set(day, { date, articles: [] });
    days.get(day).articles.push(entry);
  }
  const yesterdayDate = new Date();
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterday = yesterdayDate.toLocaleDateString('fr-FR');
  for (const [day, collection] of days) {
    const section = document.createElement('section');
    section.className = 'day-section';
    const heading = document.createElement('h2');
    heading.className = 'day-heading';
    heading.textContent = !collection.date ? 'Date inconnue' : day === today ? 'Aujourd’hui' : day === yesterday ? 'Hier' : dateFormat.format(collection.date);
    const count = document.createElement('span');
    count.textContent = ` / ${collection.articles.length}`;
    heading.append(count);
    section.append(heading);
    const list = document.createElement('div');
    list.className = 'article-list';
    for (const entry of collection.articles) list.append(articleLink(entry, sources));
    section.append(list);
    fragment.append(section);
  }
  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = state.group === 'BD' ? 'Aucune publication BD ni chapitre disponible.' : 'Aucune nouveauté dans cette catégorie sur les dernières 48 heures.';
    fragment.append(empty);
  }
  feed.replaceChildren(fragment);
}

async function load() {
  if (state.loading) return;
  state.loading = true;
  byId('feed').setAttribute('aria-busy', 'true');
  try {
    const data = await fetchData('articles');
    if (!Array.isArray(data.articles) || !Array.isArray(data.sources) || !Number.isFinite(Date.parse(data.generatedAt))) throw new Error('Données invalides');
    if (!data.sources.every(validSource) || !data.articles.every(validArticle)) throw new Error('Données invalides');
    if (JSON.stringify(state.data) !== JSON.stringify(data)) versions.news++;
    state.data = data;
    render();
  } catch {
    byId('notice').hidden = false;
    byId('notice').textContent = 'Impossible de charger les actualités. Vérifiez votre connexion puis rechargez la page.';
    if (!state.data) { byId('feed').textContent = ''; byId('updated-time').textContent = '—'; byId('updated').setAttribute('aria-label', 'Connexion interrompue'); }
  } finally {
    state.loading = false;
    byId('feed').setAttribute('aria-busy', 'false');
  }
}

tabs.forEach((button) => button.addEventListener('click', () => {
  state.group = button.dataset.group;
  tabs.forEach((tab) => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); });
  render();
}));
byId('show-sources').addEventListener('click', () => { byId('sources-dialog').showModal(); render(); });
byId('close-sources').addEventListener('click', () => byId('sources-dialog').close());
byId('sources-dialog').addEventListener('click', (event) => { if (event.target === byId('sources-dialog')) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });
document.addEventListener('visibilitychange', () => { if (!document.hidden) { load(); loadMangas(); } });
setInterval(() => { if (!document.hidden) render(); }, 60000);
setInterval(() => { if (!document.hidden) { load(); loadMangas(); } }, 300000);
load();
loadMangas();
