import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


OUT = Path("site/data.json")

# ---------------------------------------------------------
# Team configuration
#
# target_type:
#   "top"       = must finish in the top X
#   "bottom"    = must finish in the bottom X
#   "position"  = must finish exactly X
#   "promotion" = promotion target (display only)
# ---------------------------------------------------------

TEAMS = {
    # GROUP 1
    "Wrexham": {
        "bbc_name": "Wrexham",
        "url": "https://www.bbc.co.uk/sport/football/teams/wrexham/table",
        "target_type": "top",
        "target": 8,
    },
    "Stockport County": {
        "bbc_name": "Stockport County",
        "url": "https://www.bbc.co.uk/sport/football/teams/stockport-county/table",
        "target_type": "top",
        "target": 6,
    },
    "Chelsea": {
        "bbc_name": "Chelsea",
        "url": "https://www.bbc.co.uk/sport/football/teams/chelsea/table",
        "target_type": "top",
        "target": 4,
    },
    "Barnet": {
        "bbc_name": "Barnet",
        "url": "https://www.bbc.co.uk/sport/football/teams/barnet/table",
        "target_type": "top",
        "target": 7,
    },

    # GROUP 2
    "West Ham": {
        "bbc_name": "West Ham United",
        "url": "https://www.bbc.co.uk/sport/football/teams/west-ham-united/table",
        "target_type": "position",
        "target": 1,
    },
    "Luton": {
        "bbc_name": "Luton Town",
        "url": "https://www.bbc.co.uk/sport/football/teams/luton-town/table",
        "target_type": "top",
        "target": 6,
    },
    "Huddersfield": {
        "bbc_name": "Huddersfield Town",
        "url": "https://www.bbc.co.uk/sport/football/teams/huddersfield-town/table",
        "target_type": "top",
        "target": 6,
    },
    "Bristol Rovers": {
        "bbc_name": "Bristol Rovers",
        "url": "https://www.bbc.co.uk/sport/football/teams/bristol-rovers/table",
        "target_type": "top",
        "target": 7,
    },
    "Cardiff": {
        "bbc_name": "Cardiff City",
        "url": "https://www.bbc.co.uk/sport/football/teams/cardiff-city/table",
        "target_type": "bottom",
        "target": 3,
    },
    "Newport County": {
        "bbc_name": "Newport County",
        "url": "https://www.bbc.co.uk/sport/football/teams/newport-county/table",
        "target_type": "bottom",
        "target": 2,
    },

    # GROUP 3
    "Hull": {
        "bbc_name": "Hull City",
        "url": "https://www.bbc.co.uk/sport/football/teams/hull-city/table",
        "target_type": "position",
        "target": 20,
    },
    "Birmingham": {
        "bbc_name": "Birmingham City",
        "url": "https://www.bbc.co.uk/sport/football/teams/birmingham-city/table",
        "target_type": "top",
        "target": 8,
    },
    "Bromley": {
        "bbc_name": "Bromley",
        "url": "https://www.bbc.co.uk/sport/football/teams/bromley/table",
        "target_type": "bottom",
        "target": 4,
    },

    # GROUP 4
    "Wolves": {
        "bbc_name": "Wolverhampton Wanderers",
        "url": "https://www.bbc.co.uk/sport/football/teams/wolverhampton-wanderers/table",
        "target_type": "top",
        "target": 2,
    },
    "Norwich": {
        "bbc_name": "Norwich City",
        "url": "https://www.bbc.co.uk/sport/football/teams/norwich-city/table",
        "target_type": "top",
        "target": 8,
    },
    "Salford": {
        "bbc_name": "Salford City",
        "url": "https://www.bbc.co.uk/sport/football/teams/salford-city/table",
        "target_type": "top",
        "target": 3,
    },
    "Grimsby": {
        "bbc_name": "Grimsby Town",
        "url": "https://www.bbc.co.uk/sport/football/teams/grimsby-town/table",
        "target_type": "top",
        "target": 7,
    },

    # GROUP 5
    "Nottingham Forest": {
        "bbc_name": "Nottingham Forest",
        "url": "https://www.bbc.co.uk/sport/football/teams/nottingham-forest/table",
        "target_type": "top",
        "target": 10,
    },
    "Plymouth": {
        "bbc_name": "Plymouth Argyle",
        "url": "https://www.bbc.co.uk/sport/football/teams/plymouth-argyle/table",
        "target_type": "top",
        "target": 6,
    },
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0)"
    )
}


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalise_name(name):
    """Normalise a team name for comparison."""

    name = name.lower().strip()

    # Remove common punctuation
    name = re.sub(r"[.'’]", "", name)

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name)

    return name


def extract_position(first_cell):
    """
    BBC's first cell contains the position and team.

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
    Removes the league position from the first cell.

    Example:
        '14 Wrexham' -> 'Wrexham'
    """

    return re.sub(r"^\d+\s+", "", first_cell).strip()


def target_description(config):
    """Return a human-readable target."""

    target_type = config["target_type"]
    target = config["target"]

    if target_type == "top":
        return f"Top {target}"

    if target_type == "bottom":
        return f"Bottom {target}"

    if target_type == "position":
        suffix = "th"

        if target % 100 not in (11, 12, 13):
            if target % 10 == 1:
                suffix = "st"
            elif target % 10 == 2:
                suffix = "nd"
            elif target % 10 == 3:
                suffix = "rd"

        return f"{target}{suffix}"

    if target_type == "promotion":
        return "Promotion"

    return str(target)


# ---------------------------------------------------------
# Determine whether a team is currently meeting its target
# ---------------------------------------------------------

def is_on_target(position, table_size, config):

    target_type = config["target_type"]
    target = config["target"]

    if target_type == "top":
        return position <= target

    if target_type == "bottom":
        return position > table_size - target

    if target_type == "position":
        return position == target

    if target_type == "promotion":
        # Promotion is normally represented by finishing
        # in one of the promotion places. For now this is
        # treated as top 2.
        return position <= 2

    return False


# ---------------------------------------------------------
# Scrape a single team
# ---------------------------------------------------------

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
    table_size = None

    known_leagues = {
        "Premier League",
        "Championship",
        "League One",
        "League Two",
        "Scottish Premiership",
    }

    # -----------------------------------------------------
    # Find league name
    # -----------------------------------------------------

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):

        heading_text = clean(
            heading.get_text(" ", strip=True)
        )

        if heading_text in known_leagues:
            league = heading_text
            break

    # -----------------------------------------------------
    # Find the relevant table
    # -----------------------------------------------------

    for table in soup.find_all("table"):

        rows = table.find_all("tr")

        if not rows:
            continue

        matching_row = None
        valid_positions = []

        for row in rows:

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

            row_position = extract_position(first_cell)

            if row_position is not None:
                valid_positions.append(row_position)

            row_team = extract_team_name(first_cell)

            if normalise_name(row_team) == normalise_name(
                config["bbc_name"]
            ):
                matching_row = cell_text
                break

        if matching_row:

            print(
                f"Matched {team_name}: {matching_row}"
            )

            # -------------------------------------------------
            # Position
            # -------------------------------------------------

            position = extract_position(
                matching_row[0]
            )

            # -------------------------------------------------
            # Points
            #
            # BBC structure:
            # [Position Team, Played, Won, Drawn, Lost,
            #  Goals For, Goals Against, Goal Difference,
            #  Points, Form]
            # -------------------------------------------------

            if len(matching_row) > 8:

                try:
                    points = int(matching_row[8])
                except ValueError:
                    points = None

            # -------------------------------------------------
            # Number of teams in the table
            # -------------------------------------------------

            if valid_positions:
                table_size = max(valid_positions)

            break

    # ---------------------------------------------------------
    # If we didn't find the team, provide a useful error
    # ---------------------------------------------------------

    if position is None:

        raise RuntimeError(
            f"Could not find {config['bbc_name']} "
            f"on the BBC table for {team_name}"
        )

    if table_size is None:

        raise RuntimeError(
            f"Could not determine table size for {team_name}"
        )

    # ---------------------------------------------------------
    # League fallback
    # ---------------------------------------------------------

    if league is None:

        fallback_leagues = {

            "Wrexham": "Championship",
            "Stockport County": "League One",
            "Chelsea": "Premier League",
            "Barnet": "League Two",

            "West Ham": "Premier League",
            "Luton": "League One",
            "Huddersfield": "League One",
            "Bristol Rovers": "League Two",
            "Cardiff": "League One",
            "Newport County": "League Two",

            "Hull": "League One",
            "Birmingham": "Championship",
            "Bromley": "League Two",

            "Wolves": "Premier League",
            "Norwich": "Championship",
            "Salford": "League Two",
            "Grimsby": "League Two",

            "Nottingham Forest": "Premier League",
            "Plymouth": "League One",
        }

        league = fallback_leagues.get(team_name)

    # ---------------------------------------------------------
    # Target status
    # ---------------------------------------------------------

    on_target = is_on_target(
        position,
        table_size,
        config
    )

    result = {
        "name": team_name,
        "bbc_name": config["bbc_name"],
        "league": league,
        "position": position,
        "table_size": table_size,
        "points": points,
        "target_type": config["target_type"],
        "target": config["target"],
        "target_description": target_description(config),
        "on_target": on_target,
    }

    print(
        f"{team_name}: "
        f"position={position}, "
        f"table_size={table_size}, "
        f"league={league}, "
        f"points={points}, "
        f"target={target_description(config)}, "
        f"on_target={on_target}"
    )

    return result


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    teams = []

    for team_name, config in TEAMS.items():

        team = get_team_table(
            team_name,
            config
        )

        teams.append(team)

    payload = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

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
