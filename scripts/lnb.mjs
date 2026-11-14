// Read only the public LNB page's sporting data through a standard Chrome session.
// No login, token extraction, third-party package, or direct protected API call.
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
const profile = await mkdtemp(join(tmpdir(), "actu-lnb-"));
const chrome = process.env.CHROME_BIN || "google-chrome";
const args = [
  "--headless",
  "--no-sandbox",
  "--disable-gpu",
  "--disable-background-networking",
  "--no-first-run",
  "--remote-debugging-pipe",
  "--no-startup-window",
  "--user-data-dir=" + profile,
];
if (process.env.HTTPS_PROXY || process.env.HTTP_PROXY)
  args.push(
    "--proxy-server=" + (process.env.HTTPS_PROXY || process.env.HTTP_PROXY),
  );
const browser = spawn(chrome, args, {
  stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"],
});
const selected = JSON.parse(process.argv[2]);
if (
  !Number.isInteger(selected.cid) ||
  !Number.isInteger(selected.yid) ||
  selected.abbrev !== "PROB"
)
  throw Error("Compétition LNB invalide");
let id = 0,
  buffer = "",
  session,
  standings,
  matches;
const competition = { external_id: selected.cid, year: selected.yid };
const pending = new Map(),
  responses = new Map();
let resolve, reject;
const done = new Promise((yes, no) => {
  resolve = yes;
  reject = no;
});
const timer = setTimeout(
  () =>
    reject(
      Error(
        "La page publique LNB ne fournit pas les données dans les 45 secondes",
      ),
    ),
  45000,
);
function send(method, params = {}, sessionId = session) {
  return new Promise((yes, no) => {
    const seq = ++id;
    pending.set(seq, { yes, no });
    browser.stdio[3].write(
      JSON.stringify({
        id: seq,
        method,
        params,
        ...(sessionId ? { sessionId } : {}),
      }) + "\0",
    );
  });
}
async function receive(message) {
  if (message.id) {
    const p = pending.get(message.id);
    if (p) {
      pending.delete(message.id);
      message.error
        ? p.no(Error(message.error.message))
        : p.yes(message.result);
    }
    return;
  }
  if (message.sessionId !== session) return;
  const p = message.params || {};
  if (message.method === "Network.responseReceived") {
    const url = new URL(p.response.url);
    if (
      url.hostname === "api-prod.lnb.fr" &&
      p.response.status === 200 &&
      [
        "/altrstats/getStandingByCompetition",
        "/match/getHeaderMatchesV2",
      ].includes(url.pathname)
    )
      responses.set(p.requestId, url.pathname);
  }
  if (
    message.method !== "Network.loadingFinished" ||
    !responses.has(p.requestId)
  )
    return;
  const path = responses.get(p.requestId);
  responses.delete(p.requestId);
  try {
    const body = await send("Network.getResponseBody", {
      requestId: p.requestId,
    });
    const json = JSON.parse(
      body.base64Encoded
        ? Buffer.from(body.body, "base64").toString()
        : body.body,
    );
    if (!Array.isArray(json.data)) return;
    if (path.endsWith("getStandingByCompetition")) {
      const rows = json.data.filter((group) => group.title === "PROB");
      if (rows.length) standings = rows;
    } else matches = json.data;
    if (competition && standings && matches)
      resolve({
        competition: { id: competition.external_id, year: competition.year },
        standings,
        matches: matches.filter(
          (m) => m.competition_external_id === competition.external_id,
        ),
      });
  } catch {
    /* Some early requests are replaced during navigation. Wait for the next complete page response. */
  }
}
browser.on("error", reject);
browser.on("exit", () =>
  reject(Error("Chrome s’est arrêté avant la lecture des données LNB")),
);
browser.stdio[4].setEncoding("utf8");
browser.stdio[4].on("data", (chunk) => {
  buffer += chunk.toString();
  let end;
  while ((end = buffer.indexOf("\0")) >= 0) {
    const line = buffer.slice(0, end);
    buffer = buffer.slice(end + 1);
    try {
      receive(JSON.parse(line)).catch(reject);
    } catch {
      reject(Error("Réponse Chrome invalide"));
    }
  }
});
try {
  const target = await send(
    "Target.createTarget",
    { url: "about:blank" },
    null,
  );
  session = (
    await send(
      "Target.attachToTarget",
      { targetId: target.targetId, flatten: true },
      null,
    )
  ).sessionId;
  await send("Network.enable");
  await send("Page.enable");
  const query = new URLSearchParams({
    did: selected.did,
    abbrev: "PROB",
    yid: selected.yid,
    cid: selected.cid,
  });
  await send("Page.navigate", {
    url: "https://lnb.fr/fr/standings/elite2?" + query,
  });
  console.log(JSON.stringify(await done));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  clearTimeout(timer);
  browser.kill("SIGTERM");
  await rm(profile, {
    recursive: true,
    force: true,
    maxRetries: 3,
    retryDelay: 100,
  });
}
