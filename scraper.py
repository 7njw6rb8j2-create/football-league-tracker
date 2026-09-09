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
        "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0)"
    )
}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_position(first_cell):
    """
    BBC's first table cell contains both the position and team name.

    Example:
        '14 Wrexham'

    Returns:
        14
    """

    match = re.match(r"^(\d+)\s+", first_cell)

    if match:
        return int(match.group(1))

    return None


def extract_team_name(first_cell):
    """
    Removes the position from the first BBC table cell.

    Example:
        '14 Wrexham' -> 'Wrexham'
    """

    return re.sub(r"^\d+\s+", "", first_cell).strip()


def get_team_table(team_name, config):

    print(f"Fetching {team_name}...")

    response = requests.get(
        config["url"],
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    league = None
    position = None
    points = None

    # ---------------------------------------------------------
    # Find the league name
    # ---------------------------------------------------------

    known_leagues = {
        "Premier League",
        "Championship",
        "League One",
        "League Two",
        "Scottish Premiership",
    }

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):

        heading_text = clean(
            heading.get_text(" ", strip=True)
        )

        if heading_text in known_leagues:
            league = heading_text
            break

    # ---------------------------------------------------------
    # Find the team's row
    # ---------------------------------------------------------

    for row in soup.find_all("tr"):

        cells = row.find_all(["th", "td"])

        if not cells:
            continue

        cell_text = [
            clean(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        if not cell_text:
            continue

        first_cell = cell_text[0]

        # BBC puts the position and team together:
        #
        # ['14 Wrexham', '6', '1', '4', '1', '7', '5', '2', '7', ...]
        #
        # Therefore:
        # index 0 = position + team
        # index 1 = played
        # index 2 = won
        # index 3 = drawn
        # index 4 = lost
        # index 5 = goals for
        # index 6 = goals against
        # index 7 = goal difference
        # index 8 = points

        row_team = extract_team_name(first_cell)

        if row_team.lower() != team_name.lower():
            continue

        print(f"Matched {team_name}: {cell_text}")

        position = extract_position(first_cell)

        # Points are the 9th entry in the BBC table row.
        if len(cell_text) > 8:
            try:
                points = int(cell_text[8])
            except ValueError:
                points = None

        break

    # ---------------------------------------------------------
    # Validate the result
    # ---------------------------------------------------------

    if position is None:
        raise RuntimeError(
            f"Could not determine the league position of {team_name}"
        )

    # If BBC doesn't expose the league heading in the HTML,
    # use the known current league as a fallback.
    if league is None:

        fallback_leagues = {
            "Wrexham": "Championship",
            "Stockport County": "League One",
            "Chelsea": "Premier League",
            "Barnet": "League Two",
        }

        league = fallback_leagues.get(team_name)

    if league is None:
        raise RuntimeError(
            f"Could not determine the league for {team_name}"
        )

    print(
        f"{team_name}: "
        f"position={position}, "
        f"league={league}, "
        f"points={points}"
    )

    return {
        "name": team_name,
        "league": league,
        "target": config["target"],
        "position": position,
        "points": points,
        "on_target": position <= config["target"],
    }


def main():

    teams = []

    for team_name, config in TEAMS.items():

        team = get_team_table(
            team_name,
            config
        )

        teams.append(team)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "BBC Sport",
        "teams": teams,
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUT.write_text(
        json.dumps(
            payload,
            indent=2
        ),
        encoding="utf-8",
    )

    print()
    print("Successfully generated data.json:")
    print(
        json.dumps(
            payload,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
