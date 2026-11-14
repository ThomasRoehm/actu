/* Standings and finished games are collected on the server; no third-party browser request. */
const scoresPanel = (() => {
  const panel = document.getElementById("scores-panel");
  const content = document.getElementById("scores-content");
  const status = document.getElementById("scores-status");
  const buttons = [...panel.querySelectorAll("[data-league]")];
  let data,
    selected = "nba",
    loading = false,
    visited = false,
    failed = false,
    rendered,
    shown = false;
  const date = new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  const url = (value) => {
    try {
      const u = new URL(value);
      return ["http:", "https:"].includes(u.protocol) &&
        !u.username &&
        !u.password
        ? u.href
        : null;
    } catch {
      return null;
    }
  };
  const node = (tag, text, className) => {
    const e = document.createElement(tag);
    if (text != null) e.textContent = text;
    if (className) e.className = className;
    return e;
  };
  const number = (value) => Number.isFinite(value) && value >= 0;
  const team = (t) =>
    t &&
    typeof t.name === "string" &&
    ["rank", "wins", "losses", "ties", "pct"].every((k) => number(t[k]));
  const game = (g) =>
    g &&
    typeof g.id === "string" &&
    Number.isFinite(Date.parse(g.date)) &&
    ["home", "away"].every(
      (k) =>
        g[k] &&
        typeof g[k].name === "string" &&
        Number.isInteger(g[k].score) &&
        g[k].score >= 0,
    );
  function valid(payload) {
    return (
      payload &&
      Array.isArray(payload.leagues) &&
      payload.leagues.length === 3 &&
      ["nba", "nfl", "elite2"].every((id) =>
        payload.leagues.some((l) => l.id === id),
      ) &&
      payload.leagues.every(
        (l) =>
          typeof l.name === "string" &&
          typeof l.source === "string" &&
          url(l.url) &&
          l.standings &&
          l.results &&
          typeof l.standings.ok === "boolean" &&
          typeof l.results.ok === "boolean" &&
          (l.standings.groups == null ||
            (Array.isArray(l.standings.groups) &&
              l.standings.groups.every(
                (g) =>
                  typeof g.name === "string" &&
                  Array.isArray(g.teams) &&
                  g.teams.every(team),
              ))) &&
          (l.results.games == null ||
            (Array.isArray(l.results.games) && l.results.games.every(game))),
      )
    );
  }
  function updated(part) {
    return Number.isFinite(Date.parse(part.updatedAt))
      ? `Mis à jour le ${date.format(new Date(part.updatedAt))}`
      : "Pas encore de collecte réussie";
  }
  function table(group, league, index) {
    const wrapper = node("div", null, "standings-scroll");
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "region");
    const t = node("table", null, "standings");
    const caption = node("caption", group.name);
    caption.id = `standing-${league.id}-${index}`;
    wrapper.setAttribute("aria-labelledby", caption.id);
    const head = node("thead"),
      row = node("tr");
    const columns = [
      ["rank", "Pos.", "Position"],
      ["name", "Équipe", "Équipe"],
      ["wins", "V", "Victoires"],
      ["losses", "D", "Défaites"],
      ...(league.id === "nfl" ? [["ties", "N", "Matchs nuls"]] : []),
      ["pct", "%", "Pourcentage de victoires"],
    ];
    for (const [, label, title] of columns) {
      const th = node("th", label);
      th.scope = "col";
      th.setAttribute("aria-label", title);
      row.append(th);
    }
    head.append(row);
    const body = node("tbody");
    for (const entry of group.teams) {
      const tr = node("tr");
      for (const [key] of columns) {
        const td = node(
          key === "name" ? "th" : "td",
          key === "pct"
            ? `${entry.pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`
            : entry[key],
        );
        if (key === "name") td.scope = "row";
        tr.append(td);
      }
      body.append(tr);
    }
    t.append(caption, head, body);
    wrapper.append(t);
    return wrapper;
  }
  function render() {
    if (panel.hidden) return;
    status.textContent = failed
      ? data
        ? "Actualisation des scores impossible. Les dernières données connues restent affichées ; réessai automatique."
        : "Impossible de charger les scores. Réessai automatique."
      : data
        ? ""
        : loading
          ? "Chargement des classements et résultats…"
          : "Scores indisponibles pour le moment.";
    status.hidden = !status.textContent;
    const league = data?.leagues.find((l) => l.id === selected);
    const key = JSON.stringify(league);
    if (!league || rendered === key) return;
    rendered = key;
    const fragment = document.createDocumentFragment();
    const heading = node("div", null, "scores-heading");
    heading.append(node("h2", league.name));
    const source = node("a", `Source : ${league.source}`, "score-source");
    source.href = url(league.url);
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    heading.append(source);
    fragment.append(heading);
    const season = league.standings.season;
    if (typeof season === "string")
      fragment.append(node("p", `Saison ${season}`, "score-meta"));
    for (const kind of ["standings", "results"]) {
      const part = league[kind],
        section = node("section", null, "score-section");
      section.append(
        node("h3", kind === "standings" ? "Classement" : "Derniers résultats"),
      );
      section.append(node("p", updated(part), "score-meta"));
      if (!part.ok)
        section.append(
          node(
            "p",
            "Collecte indisponible. Les dernières données connues sont conservées.",
            "notice",
          ),
        );
      if (kind === "standings") {
        (part.groups || []).forEach((group, index) =>
          section.append(table(group, league, index)),
        );
        if (!part.groups?.length)
          section.append(node("p", "Classement indisponible.", "score-meta"));
      } else {
        section.append(
          node(
            "p",
            "Matchs terminés · Équipe à domicile en premier",
            "score-meta",
          ),
        );
        const list = node("ul", null, "score-games");
        for (const match of part.games || []) {
          const item = node("li", null, "score-game");
          const time = node(
            "time",
            date.format(new Date(match.date)),
            "score-meta",
          );
          time.dateTime = match.date;
          item.append(time);
          for (const side of ["home", "away"]) {
            const row = node("div", null, "score-team");
            row.append(
              node("span", match[side].name),
              node("strong", match[side].score),
            );
            item.append(row);
          }
          list.append(item);
        }
        section.append(list);
        if (!part.games?.length)
          section.append(
            node(
              "p",
              part.ok
                ? "Aucun match terminé dans la période consultée."
                : "Résultats indisponibles.",
              "score-meta",
            ),
          );
      }
      fragment.append(section);
    }
    // A background update must not move the table being read. Apply it on the next visit.
    if (
      content.childElementCount &&
      (scrollY > 0 || content.contains(document.activeElement))
    ) {
      rendered = undefined;
      status.textContent =
        "Des données plus récentes sont disponibles ; elles seront affichées à la prochaine ouverture de cet onglet.";
      status.hidden = false;
      return;
    }
    content.replaceChildren(fragment);
  }
  async function load() {
    if (!visited || loading) return;
    loading = true;
    render();
    try {
      const response = await fetch("data/scores.json", {
        cache: "no-cache",
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) throw Error("HTTP " + response.status);
      const payload = await response.json();
      if (!valid(payload)) throw Error("Données invalides");
      data = payload;
      failed = false;
    } catch {
      failed = true;
    } finally {
      loading = false;
      render();
    }
  }
  buttons.forEach((button) =>
    button.addEventListener("click", () => {
      selected = button.dataset.league;
      buttons.forEach((b) =>
        b.setAttribute("aria-pressed", String(b === button)),
      );
      content.replaceChildren();
      rendered = undefined;
      render();
    }),
  );
  return {
    show(active) {
      const entering = active && !shown;
      shown = active;
      panel.hidden = !active;
      if (entering) {
        if (!visited) {
          visited = true;
          load();
        } else {
          content.replaceChildren();
          rendered = undefined;
          render();
        }
      }
    },
    load,
  };
})();
