"""
Golf Pool - Live Score Fetch & Publish
----------------------------------------
Run this on a schedule (every 5 minutes during tournament rounds) to:
  1. Pull live scores from the Data Golf API
  2. Load this tournament's Pairings (entrant -> 3 golfers)
  3. Compute each Pairing's live total, applying the pool's cut rule
  4. Write results.json (safe to publish publicly - contains NO API key)

Environment variable required:
  DATAGOLF_API_KEY   - set as a GitHub Actions secret, never hard-coded here

** STATUS **
  1. tour=pga CONFIRMED correct for majors (including The Open) per Data Golf's
     official API docs (datagolf.com/api-access) - majors are not a separate tour
     option; they're covered under tour=pga since they run through the PGA Tour
     schedule. No change needed here.
  2. Live call made against the real endpoint on Thursday, July 16, 2026 (Round 1
     of The Open, Royal Birkdale) and CONFIRMED the actual response shape:
         {"data": [ {...player...}, ... ], "info": {"current_round": 1, ...}}
     Records live under payload["data"] - a flat list, not further nested.
     IMPORTANT CORRECTION: the per-player field names are current_pos and
     current_score, NOT position and score as originally assumed from the
     Scottish Open export. All other fields (player_name "Last, First", course,
     thru, today) matched the original assumption exactly. Fixed below.
  3. pairings.json is now generated from the Master file's Pairings sheet via
     pairings_export.py (run after every Participant Data / Pairings rebuild).
     Records include both entrant_full_name and label per the leaderboard's
     search requirement.
"""

import os
import json
import urllib.request
import urllib.error

DATAGOLF_API_KEY = os.environ.get('DATAGOLF_API_KEY')
LIVE_ENDPOINT = 'https://feeds.datagolf.com/preds/in-play'
TOUR = 'pga'  # ASSUMPTION - confirm this covers majors, see note above

PAIRINGS_FILE = 'pairings.json'   # exported from Master's Pairings sheet (future build)
OUTPUT_FILE = 'results.json'

from scoring_engine import parse_live_rows, build_leaderboard, normalize_name


def fetch_live_data():
    if not DATAGOLF_API_KEY:
        raise RuntimeError('DATAGOLF_API_KEY environment variable is not set.')

    url = f'{LIVE_ENDPOINT}?tour={TOUR}&file_format=json&key={DATAGOLF_API_KEY}'
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Data Golf API returned HTTP {e.code}: {e.read().decode(errors="ignore")}')

    # Confirmed via a live call on 2026-07-16 (see STATUS note above): records live
    # under payload["data"]; real per-player fields are current_pos / current_score,
    # not position / score. Kept the isinstance(list) fallback defensively in case
    # Data Golf ever changes the wrapper, but the dict-with-"data" shape is confirmed.
    rows = []
    records = payload if isinstance(payload, list) else payload.get('data', [])
    for rec in records:
        rows.append((
            rec.get('current_pos'),
            rec.get('player_name'),
            rec.get('course'),
            rec.get('current_score'),
            rec.get('thru'),
            rec.get('today'),
        ))
    return rows


def main():
    rows = fetch_live_data()
    live_data = parse_live_rows(rows)

    with open(PAIRINGS_FILE) as f:
        pairings = json.load(f)

    result = build_leaderboard(pairings, live_data)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Published {len(result['leaderboard'])} pairings to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
