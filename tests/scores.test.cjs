// Optional Playwright browser tests, no production dependency.
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
    const p = await b.newPage();
    let payload = {
        generatedAt: "2026-11-14T18:00:00Z",
        leagues: ["nba", "nfl", "elite2"].map((id) => ({
          id,
          name: id.toUpperCase(),
          source: "Source test",
          url: "https://example.com",
          standings: {
            ok: true,
            updatedAt: "2026-11-14T18:00:00Z",
            season: "2026/2027",
            groups: [
              {
                name: "Groupe test",
                teams: [
                  {
                    id: "1",
                    rank: 1,
                    name: "Équipe un",
                    wins: 6,
                    losses: 2,
                    ties: 0,
                    pct: 75,
                  },
                  {
                    id: "2",
                    rank: 2,
                    name: "SCABB Saint-Étienne Métropole",
                    wins: 5,
                    losses: 3,
                    ties: 0,
                    pct: 62.5,
                  },
                ],
              },
            ],
          },
          results: {
            ok: true,
            updatedAt: "2026-11-14T18:00:00Z",
            games: [
              {
                id: "match",
                date: "2026-11-13T19:00:00Z",
                home: { name: "Équipe un", score: 89 },
                away: { name: "Équipe deux", score: 85 },
              },
            ],
          },
        })),
      },
      failed = false,
      scoreRequests = 0,
      external = 0;
    const errors = [];
    p.on("pageerror", (e) => errors.push(e.message));
    await p.clock.install({ time: new Date(payload.generatedAt) });
    await p.route("**/*", async (r) => {
      const u = new URL(r.request().url());
      if (u.origin !== "http://actu.test") {
        external++;
        return r.abort();
      }
      if (u.pathname === "/data/scores.json") {
        scoreRequests++;
        if (failed) return r.abort();
        return r.fulfill({ json: payload });
      }
      if (u.pathname === "/data/articles.json")
        return r.fulfill({
          json: {
            generatedAt: "2026-11-14T18:00:00Z",
            sources: [
              {
                id: "gnt",
                name: "Source test",
                group: "Tech",
                url: "https://example.com",
                ok: true,
              },
            ],
            articles: [
              {
                source: "gnt",
                title: "Actualité test",
                url: "https://example.com/article",
                publishedAt: "2026-11-14T17:00:00Z",
              },
            ],
          },
        });
      if (u.pathname === "/data/mangas.json")
        return r.fulfill({ json: { mangas: [] } });
      const f = path.join(root, u.pathname === "/" ? "index.html" : u.pathname);
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
              ".svg": "image/svg+xml",
              ".png": "image/png",
              ".jpg": "image/jpeg",
            }[path.extname(f)] || "application/octet-stream",
        });
      } catch {
        await r.fulfill({ status: 404, body: "" });
      }
    });
    await p.goto("http://actu.test/");
    await p.waitForFunction(() => state.data && state.mangas);
    assert.equal(scoreRequests, 0, "Scores load only when requested");
    await p.locator('[data-group="Scores"]').click();
    await p.waitForFunction(
      () => document.querySelectorAll(".standings tbody tr").length > 0,
    );
    assert.equal(await p.locator("#feed").isVisible(), false);
    assert.equal(await p.locator(".standings tbody tr").count(), 2);
    for (const theme of ["light", "dark"]) {
      await p.emulateMedia({ colorScheme: theme });
      for (const width of [320, 390, 1280]) {
        await p.setViewportSize({ width, height: 900 });
        for (const [league, count] of [
          ["nba", 2],
          ["nfl", 2],
          ["elite2", 2],
        ]) {
          await p.locator(`[data-league="${league}"]`).click();
          assert.equal(await p.locator(".standings tbody tr").count(), count);
          assert.ok((await p.locator(".score-game").count()) > 0);
          assert.equal(
            await p.evaluate(
              () => document.documentElement.scrollWidth > innerWidth,
            ),
            false,
          );
          assert.equal(
            (await p.locator('.standings th[scope="col"]').count()) > 0,
            true,
          );
        }
        if (width === 390 && theme === "light")
          await p.screenshot({
            path: `/tmp/actu-scores-fixture-${engine}.png`,
          });
      }
    }
    await p.evaluate(() => {
      window.firstScore = document.querySelector(".score-game");
      render();
    });
    assert.equal(
      await p.evaluate(
        () => window.firstScore === document.querySelector(".score-game"),
      ),
      true,
      "News updates do not rebuild Scores",
    );
    await p.locator("#show-sources").click();
    assert.ok((await p.locator(".source-row").count()) > 0);
    await p.keyboard.press("Escape");
    failed = true;
    await p.evaluate(() => scoresPanel.load());
    assert.match(await p.locator("#scores-status").innerText(), /impossible/);
    assert.equal(await p.locator(".standings tbody tr").count(), 2);
    failed = false;
    payload.leagues.find((l) => l.id === "elite2").standings.ok = false;
    await p.evaluate(() => scrollTo(0, 0));
    await p.evaluate(() => scoresPanel.load());
    assert.match(
      await p.locator("#scores-content .notice").first().innerText(),
      /indisponible/,
    );
    assert.equal(await p.locator(".standings tbody tr").count(), 2);
    await p.setViewportSize({ width: 320, height: 900 });
    await p.evaluate(() => (document.documentElement.style.fontSize = "32px"));
    assert.equal(
      await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
    );
    await p.locator('[data-group="Tech"]').click();
    assert.equal(await p.locator("#scores-panel").isVisible(), false);
    assert.ok((await p.locator("#feed .article").count()) > 0);
    assert.equal(external, 0, "No ESPN/LNB browser requests");
    assert.deepEqual(errors, []);
    console.log(
      engine,
      "scores, tables, sources, mobile, zoom, failure recovery and privacy: OK",
    );
    await b.close();
  }
})();
