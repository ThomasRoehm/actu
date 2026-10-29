const state = { data: null, mangas: null, mangaError: false, mangaLoading: false, group: 'Tech', loading: false };
const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
const clockFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const safeUrl = (value) => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } };

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
    group.textContent = `${source.group} · ${source.language === 'en' ? 'Anglais' : 'Français'}`;
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

function renderMangas() {
  const section = byId('manga-feed');
  section.hidden = state.group !== 'BD';
  if (section.hidden) return;
  section.replaceChildren();
  if (!state.mangas) {
    const info = document.createElement('p');
    info.className = 'manga-info';
    info.textContent = state.mangaError ? 'Impossible de charger les mangas. Réessayez en rechargeant la page.' : 'Chargement des derniers chapitres…';
    section.append(info);
    return;
  }
  if (state.mangaError || state.mangas.some((manga) => !manga.ok)) {
    const notice = document.createElement('p');
    notice.className = 'notice';
    notice.textContent = 'Certaines vérifications sont indisponibles. Les derniers chapitres connus restent affichés.';
    section.append(notice);
  }
  const list = document.createElement('div');
  list.className = 'article-list';
  const mangas = [...state.mangas].sort((first, second) => (mangaDate(second)?.date.getTime() || 0) - (mangaDate(first)?.date.getTime() || 0) || first.title.localeCompare(second.title));
  for (const manga of mangas) {
    const link = document.createElement('a');
    link.className = 'article manga-article';
    link.href = safeUrl(manga.url) || safeUrl(manga.pageUrl) || '#';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.title = manga.lastSuccessAt ? `Dernière vérification réussie : ${new Date(manga.lastSuccessAt).toLocaleString('fr-FR')}` : 'Chapitre non vérifié';
    const metadata = document.createElement('div');
    metadata.className = 'article-metadata';
    const title = document.createElement('span');
    title.className = 'article-title';
    title.textContent = `${manga.title} — ${manga.chapter || 'Chapitre indisponible'}`;
    const source = document.createElement('span');
    source.className = 'article-source';
    const sourceName = manga.source === 'otl' ? 'OTL' : 'MangaKatana';
    source.textContent = manga.ok ? sourceName : `${sourceName} · à vérifier`;
    const date = document.createElement('span');
    date.className = 'article-time';
    const displayedDate = mangaDate(manga);
    date.textContent = displayedDate ? `${displayedDate.observed ? 'Repéré le ' : ''}${displayedDate.date.toLocaleDateString('fr-FR')}` : 'Date inconnue';
    if (displayedDate?.observed) date.title = `Date annoncée par ${sourceName} : ${manga.publishedDate}. Chapitre déjà disponible lors de la collecte.`;
    metadata.append(icon({ id: manga.source === 'otl' ? 'otl' : 'mangakatana', name: sourceName }), source, date);
    link.append(metadata, title);
    list.append(link);
  }
  section.append(list);
}

async function loadMangas() {
  if (state.mangaLoading) return;
  state.mangaLoading = true;
  try {
    const response = await fetch(`data/mangas.json?t=${Date.now()}`, { cache: 'no-store', signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.mangas)) throw new Error('Données invalides');
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
  document.querySelectorAll('[data-group]').forEach((button) => {
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
  byId('updated').title = `Dernière collecte : ${generated.toLocaleString('fr-FR')}. Collecte programmée toutes les 5 minutes, sous réserve des délais de GitHub.`;
  const failed = state.data.sources.filter((source) => !source.ok).length;
  const stale = now - generated.getTime() > 3600000;
  byId('notice').hidden = !failed && !stale;
  byId('notice').textContent = [stale ? 'La collecte a du retard. Les actualités de plus de 48 heures sont masquées, sauf les dernières publications BD.' : '', failed ? `${failed} source${failed > 1 ? 's' : ''} temporairement indisponible${failed > 1 ? 's' : ''}. Détails dans « Sources » ; les articles sont conservés pendant 48 heures, sans expiration pour la dernière publication BD.` : ''].filter(Boolean).join(' ');
  const feed = byId('feed');
  feed.replaceChildren();
  const days = new Map();
  for (const article of filtered) {
    const date = new Date(article.publishedAt);
    const day = date.toLocaleDateString('fr-FR');
    if (!days.has(day)) days.set(day, { date, articles: [] });
    days.get(day).articles.push(article);
  }
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
      const metadata = document.createElement('div');
      metadata.className = 'article-metadata';
      const title = document.createElement('span');
      title.className = 'article-title';
      title.textContent = article.title;
      const label = document.createElement('span');
      label.className = 'article-source';
      label.textContent = source.name;
      const time = document.createElement('time');
      time.className = 'article-time';
      time.dateTime = article.publishedAt;
      time.textContent = clockFormat.format(date);
      metadata.append(icon(source), label, time);
      link.append(metadata, title);
      list.append(link);
    }
    section.append(list);
    feed.append(section);
  }
  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = state.group === 'BD' ? 'Aucune publication BD. Les mangas sont affichés séparément ci-dessus.' : 'Aucune nouveauté dans cette catégorie sur les dernières 48 heures.';
    feed.append(empty);
  }
  renderSources(state.data.sources, articles);
}

async function load() {
  if (state.loading) return;
  state.loading = true;
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
    byId('notice').textContent = 'Impossible de charger les actualités. Vérifiez votre connexion puis rechargez la page.';
    if (!state.data) { byId('feed').textContent = ''; byId('updated-time').textContent = '—'; byId('updated').setAttribute('aria-label', 'Connexion interrompue'); }
  } finally {
    state.loading = false;
    byId('feed').setAttribute('aria-busy', 'false');
  }
}

document.querySelectorAll('[data-group]').forEach((button) => button.addEventListener('click', () => {
  state.group = button.dataset.group;
  document.querySelectorAll('[data-group]').forEach((tab) => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); });
  render();
}));
byId('show-sources').addEventListener('click', () => byId('sources-dialog').showModal());
byId('close-sources').addEventListener('click', () => byId('sources-dialog').close());
byId('sources-dialog').addEventListener('click', (event) => { if (event.target === byId('sources-dialog')) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });
document.addEventListener('visibilitychange', () => { if (!document.hidden) { load(); loadMangas(); } });
setInterval(render, 60000);
setInterval(() => { if (!document.hidden) { load(); loadMangas(); } }, 300000);
load();
loadMangas();
