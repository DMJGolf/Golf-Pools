"""
Golf Pool - Pairings Export
----------------------------
Reads the Master workbook's Pairings sheet (built from Intake, verified against
Master Column P) and produces pairings.json for the live-scoring pipeline.

Usage:
    python pairings_export.py Open_Master_2026_2.xlsx pairings.json

Output format (list of dicts, one per Pairing):
    {
        "entrant_full_name": "Amy Foley",
        "label": "Amy F",
        "pairing_id": "Amy F-1",
        "golfers": ["Scottie Scheffler", "Chris Gotterup", "Viktor Hovland"]
    }

entrant_full_name and label are both included per the leaderboard's search
requirement (entrants may search by either). Full names are pulled from the
Master sheet's compact Entrant First/Last columns (H, I), matched to the
Pairings sheet by label.

Blocks with fewer than 3 golfers (e.g. an entrant whose data is still pending,
like Tracy Brown as of this build) are skipped and reported, not written as
partial/broken entries.
"""

import sys
import json
import openpyxl


def build_label_to_name_map(master_ws):
    """Forward-fill Master!H (First), I (Last) against J (label) -> {label: 'First Last'}"""
    mapping = {}
    cur_first = cur_last = None
    r = 2
    while master_ws.cell(r, 10).value:  # column J = label
        h = master_ws.cell(r, 8).value
        i = master_ws.cell(r, 9).value
        j = master_ws.cell(r, 10).value
        if h:
            cur_first, cur_last = h.strip(), i.strip()
        if j not in mapping:
            mapping[j] = f"{cur_first.strip()} {cur_last.strip()}"
        r += 1
    return mapping


def export_pairings(workbook_path, output_path):
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    master_ws = wb['Master']
    pairings_ws = wb['Pairings']

    label_to_name = build_label_to_name_map(master_ws)

    records = []
    skipped = []
    r = 3  # Pairings sheet data starts at row 3 (row1=title, row2=headers)
    max_row = pairings_ws.max_row
    while r <= max_row:
        label = pairings_ws.cell(r, 1).value
        pairing_num = pairings_ws.cell(r, 2).value
        if label:
            g1 = pairings_ws.cell(r, 4).value
            g2 = pairings_ws.cell(r + 1, 4).value
            g3 = pairings_ws.cell(r + 2, 4).value
            golfers = [g for g in (g1, g2, g3) if g]
            if len(golfers) != 3:
                skipped.append((label, pairing_num))
            else:
                full_name = label_to_name.get(label, label)
                records.append({
                    "entrant_full_name": full_name,
                    "label": label,
                    "pairing_id": f"{label}-{pairing_num}",
                    "golfers": golfers,
                })
            r += 4  # advance to next block (3 golfer rows + 1 blank separator)
        else:
            r += 1

    with open(output_path, 'w') as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} pairings to {output_path}")
    if skipped:
        print(f"Skipped {len(skipped)} incomplete pairing(s) (no golfer data yet):")
        for label, pnum in skipped:
            print(f"  - {label}, Pairing {pnum}")

    return records, skipped


if __name__ == '__main__':
    workbook_path = sys.argv[1] if len(sys.argv) > 1 else 'Open_Master_2026_2.xlsx'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'pairings.json'
    export_pairings(workbook_path, output_path)
