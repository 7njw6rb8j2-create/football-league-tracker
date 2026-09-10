import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT = Path("site/data.json")

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

ALIASES = {
    "Stockport": "Stockport County",
    "Stockport County": "Stockport County",
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
    "Plymouth Argyle": "Plymouth",
    "Plymouth": "Plymouth",
    "Newport County": "Newport County",
    "Bristol Rovers": "Bristol Rovers",
    "Barnet": "Barnet",
    "Chelsea": "Chelsea",
    "Wrexham": "Wrexham",
    "Bromley": "Bromley",
}

GOALSCORERS = {
    "E. Haaland": 25,
    "A. Semenyo": 15,
    "M. Gibbs-White": 10,
    "B. Mbeumo": 10,
    "M. Rogers": 10,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0)"
}

TABLES_URL = "https://www.bbc.co.uk/sport/football/tables"
SCORERS_URL = "https://www.bbc.co.uk/sport/football/premier-league/top-scorers"


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def extract_position(first_cell):
    match = re.match(r"^(\d+)\s+", first_cell)
    return int(match.group(1)) if match else None


def find_team(first_cell):
    name = re.sub(r"^\d+\s+", "", first_cell).strip()

    for alias, canonical in ALIASES.items():
        if name.lower() == alias.lower():
            return canonical

    return None


def extract_rows(soup):
    found = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])

            if len(cells) < 2:
                continue

            texts = [
                clean(c.get_text(" ", strip=True))
                for c in cells
            ]

            if not texts:
                continue

            team = find_team(texts[0])

            if not team or team not in TEAMS:
                continue

            position = extract_position(texts[0])

            if position is None:
                continue

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


def extract_goalscorers(soup):
    found = {}

    # Start every tracked player at 0 goals.
    # If they appear on the BBC list, their actual total
    # will replace this value below.
    for player, target in GOALSCORERS.items():
        found[player] = {
            "name": player,
            "goals": 0,
            "target": target,
            "on_target": False,
        }

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            row_text = clean(row.get_text(" ", strip=True))

            if not row_text:
                continue

            matched_player = None

            for player in GOALSCORERS:
                if player.lower() in row_text.lower():
                    matched_player = player
                    break

            # This row doesn't contain one of our tracked players.
            if not matched_player:
                continue

            # BBC scorer rows contain:
            # rank, name, team, goals, goals, assists, assists, etc.
            #
            # The second integer in the row is the goal total.
            numbers = re.findall(
                r"(?<![\d.])\d+(?![\d.])",
                row_text
            )

            if len(numbers) < 2:
                continue

            try:
                goals = int(numbers[1])
            except ValueError:
                continue

            target = GOALSCORERS[matched_player]

            found[matched_player] = {
                "name": matched_player,
                "goals": goals,
                "target": target,
                "on_target": goals >= target,
            }

            print(
                f"Matched goalscorer "
                f"{matched_player}: {goals} goals"
            )

    return found


def main():
    # ---------------------------------------------------------
    # LEAGUE TABLES
    # ---------------------------------------------------------

    response = requests.get(
        TABLES_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    found = extract_rows(soup)

    missing = [
        name
        for name in TEAMS
        if name not in found
    ]

    if missing:
        raise RuntimeError(
            "Could not find these teams on BBC tables: "
            + ", ".join(missing)
        )

    # ---------------------------------------------------------
    # PREMIER LEAGUE GOALSCORERS
    # ---------------------------------------------------------

    scorer_response = requests.get(
        SCORERS_URL,
        headers=HEADERS,
        timeout=30
    )

    scorer_response.raise_for_status()

    scorer_soup = BeautifulSoup(
        scorer_response.text,
        "html.parser"
    )

    # Players who aren't present on the BBC list are
    # automatically given 0 goals by this function.
    scorers = extract_goalscorers(scorer_soup)

    # ---------------------------------------------------------
    # BUILD DATA FILE
    # ---------------------------------------------------------

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": TABLES_URL,
        "scorers_source": SCORERS_URL,
        "teams": [],
        "goalscorers": list(scorers.values()),
    }

    for name, cfg in TEAMS.items():
        item = found[name]

        payload["teams"].append({
            "name": name,
            "league": cfg["league"],
            "position": item["position"],
            "points": item["points"],
        })

    # ---------------------------------------------------------
    # WRITE DATA.JSON
    # ---------------------------------------------------------

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8"
    )

    print("Successfully generated data.json")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
