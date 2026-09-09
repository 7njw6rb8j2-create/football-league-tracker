import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


OUT = Path("site/data.json")

TEAMS = {
    "Wrexham": {
        "url": "https://www.bbc.co.uk/sport/football/teams/wrexham/table",
        "target": 8,
    },
    "Stockport County": {
        "url": "https://www.bbc.co.uk/sport/football/teams/stockport-county/table",
        "target": 6,
    },
    "Chelsea": {
        "url": "https://www.bbc.co.uk/sport/football/teams/chelsea/table",
        "target": 4,
    },
    "Barnet": {
        "url": "https://www.bbc.co.uk/sport/football/teams/barnet/table",
        "target": 7,
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0; "
        "+https://github.com/)"
    )
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_team_table(team_name, config):
    print(f"Fetching {team_name}...")

    response = requests.get(
        config["url"],
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # ---------------------------------------------------------
    # Find the league name.
    # BBC puts the competition name immediately before
    # the table.
    # ---------------------------------------------------------

    league = None

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = clean(heading.get_text(" ", strip=True))

        if text in {
            "Premier League",
            "Championship",
            "League One",
            "League Two",
            "Scottish Premiership",
        }:
            league = text
            break

    # ---------------------------------------------------------
    # Find the row containing the team.
    # ---------------------------------------------------------

    team_position = None
    points = None

    # BBC uses table rows for the league standings.
    for row in soup.find_all("tr"):
        row_text = clean(row.get_text(" ", strip=True))

        if not row_text:
            continue

        # Match the team name.
        if team_name.lower() not in row_text.lower():
            continue

        cells = row.find_all(["th", "td"])

        if not cells:
            continue

        cell_text = [
            clean(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        print(f"Matched {team_name}: {cell_text}")

        # BBC table structure:
# [Position, Team, Played, Won, Drawn, Lost, ...]
# Position is the first entry.
if cell_text and re.fullmatch(r"\d{1,2}", cell_text[0]):
    team_position = int(cell_text[0])

        # Points are normally the final numeric value before
        # the form indicators.
        numeric_values = []

        for value in cell_text:
            if re.fullmatch(r"-?\d+", value):
                numeric_values.append(int(value))

        if numeric_values:
            points = numeric_values[-1]

        break

    # ---------------------------------------------------------
    # Fallback: look for the team's BBC link and inspect its
    # surrounding parent elements.
    # ---------------------------------------------------------

    if team_position is None:

        for link in soup.find_all("a"):
            link_text = clean(link.get_text(" ", strip=True))

            if link_text.lower() != team_name.lower():
                continue

            parent = link

            for _ in range(5):
                parent = parent.parent

                if parent is None:
                    break

                text = clean(parent.get_text(" ", strip=True))

                if team_name.lower() not in text.lower():
                    continue

                numbers = [
                    int(x)
                    for x in re.findall(r"(?<!\d)\d{1,2}(?!\d)", text)
                    if 1 <= int(x) <= 30
                ]

                if numbers:
                    team_position = numbers[0]

                break

            if team_position is not None:
                break

    if team_position is None:
        raise RuntimeError(
            f"Could not determine the league position of {team_name}"
        )

    if league is None:
        raise RuntimeError(
            f"Could not determine the league for {team_name}"
        )

    print(
        f"{team_name}: position={team_position}, "
        f"league={league}, points={points}"
    )

    return {
        "name": team_name,
        "league": league,
        "target": config["target"],
        "position": team_position,
        "points": points,
    }


def main():

    teams = []

    for team_name, config in TEAMS.items():
        team = get_team_table(team_name, config)
        teams.append(team)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "BBC Sport",
        "teams": teams,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    OUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    print()
    print("Successfully generated:")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
