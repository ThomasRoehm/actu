"""Public standings and completed results. Failed sections keep their last good data."""
import concurrent.futures
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import urllib.parse

from scripts.collect import ROOT, UTC, canonical_url, fetch, parse_date

LEAGUES = {
    'nba': {'name': 'NBA', 'sport': 'basketball', 'source': 'ESPN', 'url': 'https://www.espn.com/nba/standings', 'days': 7},
    'nfl': {'name': 'NFL', 'sport': 'football', 'source': 'ESPN', 'url': 'https://www.espn.com/nfl/standings', 'days': 21},
    'elite2': {'name': 'Élite 2', 'source': 'LNB', 'url': 'https://lnb.fr/fr/standings/elite2'},
}


def integer(value):
    if isinstance(value, bool):
        raise ValueError('Nombre invalide')
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError('Nombre invalide')
    return int(number)


def label(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Nom manquant')
    return value.strip()


def espn_standings(payload):
    groups = []
    names = {'Eastern Conference': 'Conférence Est', 'Western Conference': 'Conférence Ouest',
             'American Football Conference': 'AFC', 'National Football Conference': 'NFC'}
    for group in payload['children']:
        teams = []
        for entry in group['standings']['entries']:
            stats = {s['name']: s.get('value') for s in entry['stats']}
            pct = float(stats['winPercent'])
            if not math.isfinite(pct) or not 0 <= pct <= 1:
                raise ValueError('Pourcentage invalide')
            teams.append({'id': str(entry['team']['id']), 'name': label(entry['team']['displayName']),
                          'rank': integer(stats['playoffSeed']), 'wins': integer(stats['wins']),
                          'losses': integer(stats['losses']), 'ties': integer(stats.get('ties', 0)), 'pct': round(pct * 100, 1)})
        if not teams or any(t['rank'] < 1 for t in teams):
            raise ValueError('Classement vide ou invalide')
        groups.append({'name': names.get(group['name'], group['name']), 'teams': sorted(teams, key=lambda t: t['rank'])})
    if not groups:
        raise ValueError('Aucun classement reconnu')
    return {'season': label(payload['season']['displayName']), 'groups': groups}


def espn_results(payload, now):
    if not isinstance(payload.get('events'), list):
        raise ValueError('Calendrier non reconnu')
    games = []
    for event in payload['events']:
        for competition in event.get('competitions', []):
            if competition.get('status', event.get('status', {})).get('type', {}).get('completed') is not True:
                continue
            date = parse_date(competition.get('date', event.get('date')))
            if not date or date > now:
                raise ValueError('Date de résultat invalide')
            sides = {c['homeAway']: c for c in competition['competitors']}
            game = {'id': str(event['id']), 'date': date.isoformat()}
            for side in ('home', 'away'):
                c = sides[side]
                score = c.get('score')
                if isinstance(score, dict):
                    score = score.get('value')
                game[side] = {'name': label(c['team']['displayName']), 'score': integer(score)}
            game['url'] = next((canonical_url(link.get('href')) for link in event.get('links', []) if canonical_url(link.get('href'))), None)
            games.append(game)
    return {'games': sorted({g['id']: g for g in games}.values(), key=lambda g: g['date'], reverse=True)[:20]}


def lnb_standings(payload):
    teams = []
    for group in payload['standings']:
        if group.get('title') != 'PROB':
            continue
        for entry in group['data']:
            teams.append({'id': str(entry['team']['external_id']), 'name': label(entry['team']['team_name']),
                          'rank': integer(entry['rank']), 'wins': integer(entry['s_wins']),
                          'losses': integer(entry['s_losses']), 'ties': 0,
                          'pct': round(float(entry['s_wins_average']), 1)})
    if len(teams) < 2 or any(t['rank'] < 1 or not math.isfinite(t['pct']) or not 0 <= t['pct'] <= 100 for t in teams):
        raise ValueError('Classement Élite 2 non reconnu')
    year = integer(payload['competition']['year'])
    return {'season': f'{year}/{year+1}', 'groups': [{'name': 'Classement général', 'teams': sorted(teams, key=lambda t: t['rank'])}]}


def lnb_results(payload, now):
    games = []
    for match in payload['matches']:
        if match.get('competition_external_id') != payload['competition']['id'] or match.get('match_status') != 'COMPLETE':
            continue
        date = parse_date(match.get('match_time_utc'))
        if not date or date > now:
            raise ValueError('Date de résultat LNB invalide')
        home, away = match['teams']
        games.append({'id': str(match['external_id']), 'date': date.isoformat(),
                      'home': {'name': label(home['team_name']), 'score': integer(home['score_string'])},
                      'away': {'name': label(away['team_name']), 'score': integer(away['score_string'])},
                      'url': None})
    return {'games': sorted({g['id']: g for g in games}.values(), key=lambda g: g['date'], reverse=True)[:20]}


def refresh(previous, collect, now):
    try:
        return {**collect(), 'ok': True, 'updatedAt': now.isoformat(), 'error': None}
    except Exception as error:
        return {**previous, 'ok': False, 'error': str(error)[:240]}


def collect_espn(league, previous, now):
    config = LEAGUES[league]
    base = f'https://site.api.espn.com/apis'
    def standings():
        return espn_standings(json.loads(fetch(f'{base}/v2/sports/{config["sport"]}/{league}/standings')))
    def results():
        if league == 'nfl':
            url = f'{base}/site/v2/sports/football/nfl/scoreboard'
            current = json.loads(fetch(url))
            week = integer(current['week']['number'])
            phase = integer(current['season']['type'])
            def previous_week(number):
                payload = json.loads(fetch(f'{url}?week={number}&seasontype={phase}'))
                if payload.get('season', {}).get('year') != current['season']['year']:
                    raise ValueError('Saison NFL incohérente')
                return espn_results(payload, now)['games']
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                games = espn_results(current, now)['games'] + [g for batch in pool.map(previous_week, range(max(1, week-2), week)) for g in batch]
        else:
            def day(offset):
                date = now - datetime.timedelta(days=offset)
                url = f'{base}/site/v2/sports/{config["sport"]}/{league}/scoreboard?dates={date:%Y%m%d}'
                return espn_results(json.loads(fetch(url)), now)['games']
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                games = [game for batch in pool.map(day, range(config['days'])) for game in batch]
        unique = {game['id']: game for game in games}
        return {'games': sorted(unique.values(), key=lambda g: g['date'], reverse=True)[:20]}
    return {**{k: config[k] for k in ('name', 'source', 'url')}, 'id': league,
            'standings': refresh(previous.get('standings', {}), standings, now),
            'results': refresh(previous.get('results', {}), results, now)}


def lnb_competition(content):
    fragments = []
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', content.decode('utf-8'), re.S):
        try:
            block = json.loads(match[1])
            if len(block) > 1 and isinstance(block[1], str):
                fragments.append(block[1])
        except ValueError:
            continue
    text = ''.join(fragments)
    for match in re.finditer(r'"division_competition_array"\s*:\s*', text):
        value, _ = json.JSONDecoder().raw_decode(text[match.end():])
        for competition in json.loads(value):
            if competition.get('abbrev') == 'PROB':
                return {key: integer(competition[key]) for key in ('did', 'cid', 'yid')} | {'abbrev': 'PROB'}
    raise ValueError('Saison Élite 2 non identifiée sur le site officiel')


def collect_lnb(previous, now):
    config = LEAGUES['elite2']
    payload = None
    failure = None
    try:
        chrome = os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium')
        if not chrome or not shutil.which('node'):
            raise RuntimeError('Chrome ou Node indisponible pour lire la page publique LNB')
        competition = lnb_competition(fetch('https://lnb.fr/fr'))
        result = subprocess.run(['node', str(ROOT / 'scripts/lnb.mjs'), json.dumps(competition)], env={**os.environ, 'CHROME_BIN': chrome},
                                capture_output=True, text=True, timeout=55, check=True)
        payload = json.loads(result.stdout)
    except Exception as error:
        failure = error
    def parse(parser):
        if failure:
            raise RuntimeError('Lecture de la page publique LNB indisponible') from failure
        return parser(payload)
    source_url = config['url']
    if payload:
        source_url += '?' + urllib.parse.urlencode({'did': 2, 'abbrev': 'PROB', 'yid': payload['competition']['year'], 'cid': payload['competition']['id']})
    return {**config, 'url': source_url, 'id': 'elite2',
            'standings': refresh(previous.get('standings', {}), lambda: parse(lnb_standings), now),
            'results': refresh(previous.get('results', {}), lambda: parse(lambda p: lnb_results(p, now)), now)}


def main():
    target = ROOT / 'data/scores.json'
    previous = json.loads(target.read_text()) if target.exists() else {'leagues': []}
    old = {league['id']: league for league in previous['leagues']}
    now = datetime.datetime.now(UTC)
    def collect(league):
        return collect_lnb(old.get(league, {}), now) if league == 'elite2' else collect_espn(league, old.get(league, {}), now)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        leagues = list(pool.map(collect, LEAGUES))
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps({'generatedAt': now.isoformat(), 'leagues': leagues}, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(target)
    for league in leagues:
        print(league['name'] + ': ' + ', '.join(part + (' OK' if league[part]['ok'] else ' indisponible') for part in ('standings', 'results')), flush=True)


if __name__ == '__main__':
    main()
