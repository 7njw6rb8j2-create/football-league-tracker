import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.bbc.co.uk/sport/football/tables"
OUT = Path("site/data.json")

# All clubs are scraped once. Groups on the webpage can then use the
# same club more than once with different targets if required.
TEAMS = {
    "Wrexham": {"league": "Championship"},
    "Stockport County": {"league": "League One"},
    "Chelsea": {"league": "Premier League"},
    "Barnet": {"league": "League Two"},
    "West Ham": {"league": "Premier League"},
    "Luton": {"league": "League One"},
    "Huddersfield": {"league": "League One"},
    "Bristol Rovers": {"league": "League Two"},
    "Cardiff": {"league": "League One"},
    "Newport County": {"league": "League Two"},
    "Hull": {"league": "Championship"},
    "Birmingham": {"league": "Championship"},
    "Bromley": {"league": "League Two"},
    "Wolves": {"league": "Premier League"},
    "Norwich": {"league": "Championship"},
    "Salford": {"league": "League Two"},
    "Grimsby": {"league": "League One"},
    "Nottingham Forest": {"league": "Premier League"},
    "Plymouth": {"league": "League One"},
}

# BBC table names -> names used by the tracker.
ALIASES = {
    "Stockport": "Stockport County",
    "West Ham United": "West Ham",
    "Luton Town": "Luton",
    "Huddersfield Town": "Huddersfield",
    "Cardiff City": "Cardiff",
    "Hull City": "Hull",
    "Birmingham City": "Birmingham",
    "Wolverhampton Wanderers": "Wolves",
    "Norwich City": "Norwich",
    "Salford City": "Salford",
    "Grimsby Town": "Grimsby",
    "Nottingham Forest": "Nottingham Forest",
    "Plymouth": "Plymouth",
    "Newport County": "Newport County",
    "Bristol Rovers": "Bristol Rovers",
    "Barnet": "Barnet",
    "Chelsea": "Chelsea",
    "Wrexham": "Wrexham",
    "Bromley": "Bromley",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0)"
}

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def find_team(first_cell):
    # BBC returns rows such as: '14 Wrexham'
    name = re.sub(r"^\d+\s+", "", first_cell).strip()
    for alias, canonical in ALIASES.items():
        if name.lower() == alias.lower():
            return canonical
    return None

def extract_position(first_cell):
    # The first entry contains the position and team, e.g. '14 Wrexham'.
    match = re.match(r"^(\d+)\s+", first_cell)
    return int(match.group(1)) if match else None

def extract_rows(soup):
    found = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue

            texts = [clean(c.get_text(" ", strip=True)) for c in cells]
            if not texts:
                continue

            team = find_team(texts[0])
            if not team or team not in TEAMS:
                continue

            position = extract_position(texts[0])
            if position is None:
                continue

            # BBC's current table structure has points as entry 8 (zero-based).
            points = None
            if len(texts) > 8:
                try:
                    points = int(texts[8])
                except ValueError:
                    pass

            found[team] = {
                "position": position,
                "points": points,
            }

            print(f"Matched {team}: {texts}")

    return found

def main():
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    found = extract_rows(soup)

    missing = [name for name in TEAMS if name not in found]
    if missing:
        raise RuntimeError(
            "Could not find these teams on BBC tables: " + ", ".join(missing)
        )

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": URL,
        "teams": [],
    }

    for name, cfg in TEAMS.items():
        item = found[name]
        payload["teams"].append({
            "name": name,
            "league": cfg["league"],
            "position": item["position"],
            "points": item["points"],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Successfully generated data.json")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
