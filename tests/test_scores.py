import datetime
import json
import unittest
from unittest.mock import patch

from scripts.scores import collect_espn, espn_results, espn_standings, integer, lnb_competition, lnb_results, lnb_standings, refresh

NOW = datetime.datetime(2026, 11, 14, 18, tzinfo=datetime.timezone.utc)


def espn_event(completed=True, score='89'):
    return {'id': 'game-1', 'date': '2026-11-13T20:00Z', 'competitions': [
        {'status': {'type': {'completed': completed}}, 'competitors': [
            {'homeAway': 'home', 'team': {'displayName': 'Domicile'}, 'score': score},
            {'homeAway': 'away', 'team': {'displayName': 'Extérieur'}, 'score': '91'}]}]}


class ScoresTests(unittest.TestCase):
    def test_only_finished_games_with_explicit_scores(self):
        payload = {'events': [espn_event(False), espn_event()]}
        games = espn_results(payload, NOW)['games']
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]['home']['score'], 89)
        self.assertEqual(games[0]['away']['name'], 'Extérieur')

    def test_missing_score_is_not_zero(self):
        with self.assertRaises((ValueError, TypeError)):
            espn_results({'events': [espn_event(score=None)]}, NOW)

    def test_score_cannot_be_negative(self):
        with self.assertRaises(ValueError):
            espn_results({'events': [espn_event(score='-1')]}, NOW)

    def test_empty_calendar_is_valid_but_missing_calendar_is_not(self):
        self.assertEqual(espn_results({'events': []}, NOW), {'games': []})
        with self.assertRaises(ValueError):
            espn_results({}, NOW)

    def test_future_completed_game_is_rejected(self):
        event = espn_event()
        event['date'] = '2027-01-01T20:00Z'
        with self.assertRaises(ValueError):
            espn_results({'events': [event]}, NOW)

    def test_standings_keep_official_conference_order_and_ties(self):
        def entry(name, rank, wins, losses, ties):
            return {'team': {'id': name, 'displayName': name}, 'stats': [
                {'name': key, 'value': value} for key, value in {'playoffSeed': rank, 'wins': wins, 'losses': losses, 'ties': ties, 'winPercent': .75}.items()]}
        value = espn_standings({'season': {'displayName': '2026'}, 'children': [
            {'name': 'American Football Conference', 'standings': {'entries': [entry('B', 2, 5, 2, 1), entry('A', 1, 6, 2, 0)]}}]})
        self.assertEqual(value['groups'][0]['name'], 'AFC')
        self.assertEqual([t['name'] for t in value['groups'][0]['teams']], ['A', 'B'])
        self.assertEqual(value['groups'][0]['teams'][1]['ties'], 1)

    def test_failed_section_preserves_data_and_last_success(self):
        old = {'games': [{'id': 'old'}], 'updatedAt': '2026-11-12T12:00Z', 'ok': True}
        def fail():
            raise RuntimeError('HTTP 503')
        result = refresh(old, fail, NOW)
        self.assertFalse(result['ok'])
        self.assertEqual(result['games'], old['games'])
        self.assertEqual(result['updatedAt'], old['updatedAt'])
        self.assertEqual(result['error'], 'HTTP 503')

    def test_success_clears_the_error(self):
        result = refresh({'ok': False, 'error': 'old'}, lambda: {'games': []}, NOW)
        self.assertTrue(result['ok'])
        self.assertIsNone(result['error'])
        self.assertEqual(result['updatedAt'], NOW.isoformat())

    def test_lnb_season_comes_from_public_site(self):
        setting = {'division_competition_array': json.dumps([{'did': 2, 'cid': 999, 'yid': 2030, 'abbrev': 'PROB'}])}
        html = '<script>self.__next_f.push(' + json.dumps([1, '1:' + json.dumps(setting)]) + ')</script>'
        self.assertEqual(lnb_competition(html.encode())['cid'], 999)
        with self.assertRaises(ValueError):
            lnb_competition(b'<html>unavailable</html>')

    def test_lnb_results_exclude_other_leagues_and_unfinished_matches(self):
        def match(id, competition, status):
            return {'external_id': id, 'competition_external_id': competition, 'match_status': status,
                    'match_time_utc': '2026-11-13T19:00:00Z', 'teams': [
                        {'team_name': 'Antibes', 'score_string': '90'}, {'team_name': 'Blois', 'score_string': '87'}]}
        payload = {'competition': {'id': 318}, 'matches': [match(1, 317, 'COMPLETE'), match(2, 318, 'IN_PROGRESS'), match(3, 318, 'COMPLETE')]}
        self.assertEqual([g['id'] for g in lnb_results(payload, NOW)['games']], ['3'])

    def test_lnb_keeps_official_ranks_including_tiebreakers(self):
        def team(name, rank):
            return {'rank': rank, 'team': {'team_name': name, 'external_id': rank}, 's_wins': 6, 's_losses': 3, 's_wins_average': 66.67}
        data = {'competition': {'year': 2026}, 'standings': [{'title': 'PROB', 'data': [team('B', 2), team('A', 1)]}]}
        self.assertEqual(lnb_standings(data)['season'], '2026/2027')
        self.assertEqual([t['name'] for t in lnb_standings(data)['groups'][0]['teams']], ['A', 'B'])

    def test_nfl_collects_previous_weeks_not_only_the_current_weekday(self):
        calls = []
        standings = {'season': {'displayName': '2026'}, 'children': [{'name': 'AFC', 'standings': {'entries': [
            {'team': {'id': '1', 'displayName': 'Équipe test'}, 'stats': [{'name': k, 'value': v} for k, v in
             {'wins': 6, 'losses': 2, 'ties': 0, 'winPercent': .75, 'playoffSeed': 1}.items()]}
        ]}}]}
        def response(url):
            calls.append(url)
            if url.endswith('/standings'):
                return json.dumps(standings).encode()
            event = espn_event()
            if 'week=8' in url:
                event['id'] = 'week-8'
            elif 'week=9' in url:
                event['id'] = 'week-9'
            return json.dumps({'season': {'year': 2026, 'type': 2}, 'week': {'number': 10}, 'events': [event]}).encode()
        with patch('scripts.scores.fetch', side_effect=response):
            result = collect_espn('nfl', {}, NOW)
        self.assertTrue(result['results']['ok'])
        self.assertEqual(len(result['results']['games']), 3)
        self.assertTrue(any('week=8' in u for u in calls))
        self.assertTrue(any('week=9' in u for u in calls))
        self.assertFalse(any('dates=' in u for u in calls))

    def test_integer_rejects_bool_and_nan(self):
        for value in (True, 'nan', '-1', '2.5'):
            with self.assertRaises(ValueError):
                integer(value)


if __name__ == '__main__':
    unittest.main()
