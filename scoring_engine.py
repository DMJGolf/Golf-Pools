"""
Golf Pool - Live Scoring Engine
--------------------------------
Takes raw Data Golf live-stats rows (position, player_name, course, score, thru, today)
and a Pairings definition (entrant -> 3 golfers), and computes a live leaderboard of
Pairing totals, applying the pool's cut rule:

    "If a golfer in your Pairing misses the cut, the Pairing will be 'cut' and no
    longer participates in the Pool."

Data Golf's own convention (confirmed from a real live-stats export): once a golfer
misses the cut, their `position` field literally becomes the string "CUT", their
`score` field freezes at their score at the time of the cut, and `thru`/`today`
become the string "null".
"""

from datetime import datetime, timezone


def normalize_name(dg_name):
    """Convert Data Golf 'Last, First' format to our Master's 'First Last' format."""
    if not dg_name or ',' not in dg_name:
        return dg_name
    last, first = [p.strip() for p in dg_name.split(',', 1)]
    return f"{first} {last}"


def parse_live_rows(rows):
    """
    rows: iterable of (position, player_name, course, score, thru, today)
    Returns: dict keyed by normalized golfer name -> {
        'position': ..., 'score': int or None, 'thru': int or None,
        'today': int or None, 'is_cut': bool
    }
    """
    live = {}
    for row in rows:
        position, player_name, course, score, thru, today = row[:6]
        name = normalize_name(player_name)
        is_cut = (str(position).strip().upper() == 'CUT')

        def clean(v):
            if v is None:
                return None
            if isinstance(v, str):
                s = v.strip()
                if s.lower() == 'null' or s == '':
                    return None
                try:
                    return int(s)
                except ValueError:
                    return v  # non-numeric string (shouldn't normally happen here)
            return v

        live[name] = {
            'position': position,
            'score': clean(score),
            'thru': clean(thru),
            'today': clean(today),
            'is_cut': is_cut,
        }
    return live


def compute_pairing(entrant_full_name, label, pairing_id, golfer_names, live_data):
    """
    golfer_names: list of 3 golfer names (First Last format) making up this Pairing
    live_data: output of parse_live_rows()

    Returns a dict describing this Pairing's live status. Both entrant_full_name
    and label are carried through so the leaderboard can search/display on either.
    """
    golfer_detail = []
    any_cut = False
    total = 0
    all_found = True

    for g in golfer_names:
        info = live_data.get(g)
        if info is None:
            # Golfer not found in live feed (shouldn't normally happen if field lists match)
            golfer_detail.append({'name': g, 'score': None, 'status': 'NOT_FOUND'})
            all_found = False
            continue

        if info['is_cut']:
            any_cut = True
            golfer_detail.append({
                'name': g,
                'score': info['score'],
                'status': 'CUT',
            })
        else:
            golfer_detail.append({
                'name': g,
                'score': info['score'] if info['score'] is not None else 0,
                'thru': info['thru'],
                'today': info['today'],
                'status': 'LIVE',
            })
            if info['score'] is not None:
                total += info['score']

    pairing_status = 'CUT' if any_cut else ('INCOMPLETE_DATA' if not all_found else 'LIVE')

    return {
        'entrant_full_name': entrant_full_name,
        'label': label,
        'pairing_id': pairing_id,
        'golfers': golfer_detail,
        'total_score': total if pairing_status == 'LIVE' else None,
        'status': pairing_status,
    }


def build_leaderboard(pairings, live_data):
    """
    pairings: list of dicts: {'entrant_full_name': str, 'label': str, 'pairing_id': str,
                               'golfers': [name1, name2, name3]}
    live_data: output of parse_live_rows()

    Returns: dict with 'last_updated' and 'leaderboard' (sorted list, LIVE pairings first
    by ascending total_score, then CUT pairings at the bottom).
    """
    results = []
    for p in pairings:
        results.append(compute_pairing(
            p['entrant_full_name'], p['label'], p['pairing_id'], p['golfers'], live_data
        ))

    live_results = [r for r in results if r['status'] == 'LIVE']
    other_results = [r for r in results if r['status'] != 'LIVE']

    live_results.sort(key=lambda r: r['total_score'])
    for i, r in enumerate(live_results, start=1):
        r['rank'] = i
    for r in other_results:
        r['rank'] = None

    return {
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'leaderboard': live_results + other_results,
    }
