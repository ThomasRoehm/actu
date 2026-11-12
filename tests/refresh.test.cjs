// Tests navigateur optionnels : nécessitent Playwright, sans dépendance pour le site.
const { chromium, webkit } = require("playwright");
const fs = require("fs"),
  path = require("path"),
  assert = require("assert/strict");
const root = path.resolve(__dirname, "..");
(async () => {
  for (const engine of ["chromium", "webkit"]) {
    const b = await (engine === "webkit"
      ? webkit.launch({
          executablePath: process.env.ACTU_WEBKIT_EXECUTABLE,
          headless: true,
        })
      : chromium.launch({
          executablePath: process.env.ACTU_CHROMIUM_EXECUTABLE,
          headless: true,
          args: ["--no-sandbox"],
        }));
    const p = await b.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    let failNews = false,
      failMangas = false;
    let data = {
      generatedAt: "2026-11-12T12:00:00Z",
      sources: [
        {
          id: "gnt",
          name: "Source test",
          group: "Tech",
          url: "https://example.com",
          ok: true,
        },
      ],
      articles: Array.from({ length: 80 }, (_, i) => ({
        source: "gnt",
        title: "Article de test " + i,
        url: "https://example.com/article/" + i,
        publishedAt: new Date(
          Date.parse("2026-11-12T12:00:00Z") - i * 60000,
        ).toISOString(),
      })),
    };
    const now = Date.parse(data.generatedAt) + 600000;
    await p.clock.install({ time: new Date(now) });
    await p.route("http://actu.test/**", async (r) => {
      let u = new URL(r.request().url()),
        f = path.join(root, u.pathname === "/" ? "index.html" : u.pathname);
      if (u.pathname === "/data/articles.json") {
        if (failNews) return r.abort();
        return r.fulfill({ json: data });
      }
      if (u.pathname === "/data/mangas.json") {
        if (failMangas) return r.abort();
        return r.fulfill({
          json: {
            mangas: [
              {
                slug: "isekai-walking.26776",
                title: "Isekai Walking",
                pageUrl: "https://example.com/manga",
                url: "https://example.com/chapter",
                chapter: "Chapitre de test",
                publishedDate: "2026-11-12",
                ok: true,
              },
            ],
          },
        });
      }
      try {
        await r.fulfill({
          body: fs.readFileSync(f),
          contentType:
            {
              ".html": "text/html",
              ".js": "application/javascript",
              ".css": "text/css",
              ".json": "application/json",
              ".woff2": "font/woff2",
              ".png": "image/png",
              ".jpg": "image/jpeg",
              ".svg": "image/svg+xml",
            }[path.extname(f)] || "application/octet-stream",
        });
      } catch {
        await r.fulfill({ status: 404, body: "" });
      }
    });
    await p.goto("http://actu.test/");
    await p.waitForFunction(() => state.data && state.mangas);
    failNews = true;
    await p.evaluate(() => load());
    assert.match(
      await p.locator("#notice").innerText(),
      /Actualisation.*impossible/,
    );
    await p.evaluate(() => loadMangas());
    assert.equal(await p.locator("#notice").isVisible(), true);
    assert.match(
      await p.locator("#notice").innerText(),
      /Actualisation.*impossible/,
    );
    await p.evaluate(() => render());
    assert.equal(await p.locator("#notice").isVisible(), true);
    failNews = false;
    await p.evaluate(() => load());
    assert.doesNotMatch(
      await p.locator("#notice").innerText(),
      /Actualisation.*impossible/,
    );
    // Position and keyboard focus survive insertion above the article being read.
    await p.locator(".article").nth(35).focus();
    await p.evaluate(() => {
      const e = document.activeElement;
      window.anchor = {
        key: e.dataset.key,
        top: e.getBoundingClientRect().top,
        node: e,
      };
    });
    const source = data.sources.find((s) => s.group === "Tech").id;
    data = {
      ...data,
      generatedAt: new Date(now).toISOString(),
      articles: [
        {
          source,
          title: "Nouvel article de test",
          url: "https://example.com/new-test",
          publishedAt: new Date(now - 1000).toISOString(),
        },
        ...data.articles,
      ],
    };
    await p.evaluate(() => load());
    const anchor = await p.evaluate(() => {
      const e = [...document.querySelectorAll(".article")].find(
        (e) => e.dataset.key === window.anchor.key,
      );
      return {
        delta: e.getBoundingClientRect().top - window.anchor.top,
        same: e === window.anchor.node,
        focused: e === document.activeElement,
      };
    });
    assert.ok(Math.abs(anchor.delta) <= 2, JSON.stringify(anchor));
    assert.equal(anchor.same, true);
    assert.equal(anchor.focused, true);
    // If the first visible item expires, keep a surviving visible neighbour in place.
    await p.evaluate(() => {
      const visible = [...document.querySelectorAll(".article")].filter(
        (e) =>
          e.getBoundingClientRect().bottom > 0 &&
          e.getBoundingClientRect().top < innerHeight,
      );
      window.removed = visible[0].dataset.key;
      window.neighbour = {
        key: visible[1].dataset.key,
        top: visible[1].getBoundingClientRect().top,
      };
    });
    const removed = await p.evaluate(() => window.removed);
    data = {
      ...data,
      articles: data.articles.filter((a) => new URL(a.url).href !== removed),
    };
    await p.evaluate(() => load());
    assert.ok(
      Math.abs(
        await p.evaluate(
          () =>
            [...document.querySelectorAll(".article")]
              .find((e) => e.dataset.key === window.neighbour.key)
              .getBoundingClientRect().top - window.neighbour.top,
        ),
      ) <= 2,
    );
    await p.evaluate(() => scrollTo(0, 0));
    data = {
      ...data,
      articles: [
        {
          source,
          title: "Encore une nouveauté",
          url: "https://example.com/top-test",
          publishedAt: new Date(now - 500).toISOString(),
        },
        ...data.articles,
      ],
    };
    await p.evaluate(() => load());
    assert.equal(await p.evaluate(() => scrollY), 0);
    await p.locator('[data-group="BD"]').click();
    failMangas = true;
    await p.evaluate(() => loadMangas());
    await p.evaluate(() => load());
    assert.match(await p.locator("#manga-feed").innerText(), /indisponibles/);
    assert.ok((await p.locator(".manga-article").count()) > 0);
    failMangas = false;
    await p.evaluate(() => loadMangas());
    // A future publication replaces an expired one without changing the count.
    const boundary = now + 60000;
    data = {
      generatedAt: new Date(boundary).toISOString(),
      sources: [
        {
          id: "gnt",
          name: "Ancienne source",
          group: "Tech",
          url: "https://example.com/old",
          ok: true,
        },
        {
          id: "clubic",
          name: "Nouvelle source",
          group: "Tech",
          url: "https://example.com/new",
          ok: true,
        },
      ],
      articles: [
        {
          source: "gnt",
          title: "Expire bientôt",
          url: "https://example.com/expiry",
          publishedAt: new Date(boundary - 48 * 3600000 + 1000).toISOString(),
        },
        {
          source: "clubic",
          title: "Publication future",
          url: "https://example.com/future",
          publishedAt: new Date(boundary + 2000).toISOString(),
        },
      ],
    };
    await pageClock(boundary);
    await p.locator('[data-group="Tech"]').click();
    await p.evaluate(() => load());
    assert.equal(
      await p.locator(".article-title").innerText(),
      "Expire bientôt",
    );
    await p.locator("#show-sources").click();
    assert.match(
      await p.locator(".source-row").first().innerText(),
      /1 article/,
    );
    await p.keyboard.press("Escape");
    await pageClock(boundary + 3000);
    await p.evaluate(() => render());
    assert.equal(
      await p.locator(".article-title").innerText(),
      "Publication future",
    );
    await p.locator("#show-sources").click();
    assert.match(
      await p.locator(".source-row").first().innerText(),
      /Aucune nouveauté/,
    );
    assert.match(
      await p.locator(".source-row").last().innerText(),
      /1 article/,
    );
    await p.keyboard.press("Escape");
    // Midnight resets local day counters even if no network response changed.
    const midnight = await p.evaluate(() => {
      const d = new Date();
      d.setHours(24, 0, 0, 0);
      return d.getTime();
    });
    await pageClock(midnight);
    await p.evaluate(() => render());
    assert.equal(
      await p.locator('[data-group="Tech"] .tab-count').innerText(),
      "0",
    );
    async function pageClock(time) {
      await p.clock.setSystemTime(new Date(time));
    }

    assert.deepEqual(errors, []);
    console.log(
      engine,
      "partial failures, recovery, inserted/removed article, focus, scroll and manga fallback: OK",
    );
    await b.close();
  }
})();
