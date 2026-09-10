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

SCORERS_URL = (
    "https://www.bbc.co.uk/sport/football/"
    "premier-league/top-scorers"
)


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def extract_position(first_cell):
    match = re.match(r"^(\d+)\s+", first_cell)

    if match:
        return int(match.group(1))

    return None


def find_team(first_cell):
    name = re.sub(
        r"^\d+\s+",
        "",
        first_cell
    ).strip()

    for alias, canonical in ALIASES.items():

        if name.lower() == alias.lower():
            return canonical

    return None


# =============================================================
# LEAGUE TABLE EXTRACTION
# =============================================================

def extract_rows(soup):
    found = {}

    # BBC can contain multiple representations of league tables.
    # We process each table separately and determine which league
    # it represents from the recognised teams inside it.

    for table_number, table in enumerate(
        soup.find_all("table"),
        start=1
    ):

        rows = table.find_all("tr")

        if not rows:
            continue

        table_entries = []

        for row in rows:

            cells = row.find_all(["th", "td"])

            if len(cells) < 2:
                continue

            texts = [
                clean(
                    cell.get_text(
                        " ",
                        strip=True
                    )
                )
                for cell in cells
            ]

            if not texts:
                continue

            team = find_team(texts[0])

            if not team:
                continue

            position = extract_position(texts[0])

            if position is None:
                continue

            points = None

            # BBC league tables normally have points in the
            # ninth column (index 8).
            if len(texts) > 8:

                try:
                    points = int(texts[8])

                except ValueError:
                    points = None

            table_entries.append({
                "team": team,
                "position": position,
                "points": points,
                "texts": texts,
            })

        if not table_entries:
            continue

        # -----------------------------------------------------
        # Determine which league this table represents.
        # -----------------------------------------------------

        league_counts = {}

        for entry in table_entries:

            team = entry["team"]
            league = TEAMS[team]["league"]

            league_counts[league] = (
                league_counts.get(league, 0) + 1
            )

        detected_league = max(
            league_counts,
            key=league_counts.get
        )

        print(
            f"Table {table_number}: detected "
            f"{detected_league}"
        )

        # -----------------------------------------------------
        # Store only teams belonging to the detected league.
        # -----------------------------------------------------

        for entry in table_entries:

            team = entry["team"]

            if TEAMS[team]["league"] != detected_league:
                print(
                    f"Ignoring {team} from table "
                    f"{table_number} because it belongs "
                    f"to {TEAMS[team]['league']}"
                )
                continue

            # -------------------------------------------------
            # IMPORTANT:
            #
            # Never overwrite an existing team.
            #
            # This prevents duplicate BBC table entries from
            # replacing the correct position with an incorrect
            # duplicate.
            # -------------------------------------------------

            if team in found:

                existing = found[team]

                print(
                    f"Ignoring duplicate entry for {team}: "
                    f"position {entry['position']} "
                    f"(already have position "
                    f"{existing['position']})"
                )

                continue

            found[team] = {
                "position": entry["position"],
                "points": entry["points"],
            }

            print(
                f"Matched {team}: "
                f"position {entry['position']}, "
                f"points {entry['points']}"
            )

    return found


# =============================================================
# GOALSCORER TABLE
# =============================================================

def find_goals_table(soup):
    """
    Find the BBC table containing the Premier League
    goalscorers.

    The BBC page can also contain an assists table.

    We specifically look for a table whose headers contain
    Goals and whose first row also contains Goals.
    """

    for table in soup.find_all("table"):

        headers = table.find_all(["th"])

        header_text = " ".join(
            clean(
                header.get_text(
                    " ",
                    strip=True
                )
            )
            for header in headers
        ).lower()

        if (
            "goals" in header_text
            and "assists" in header_text
        ):

            rows = table.find_all("tr")

            if rows:

                first_row_text = clean(
                    rows[0].get_text(
                        " ",
                        strip=True
                    )
                ).lower()

                if "goals" in first_row_text:
                    return table

        elif "goals" in header_text:

            return table

    # Fallback.
    for table in soup.find_all("table"):

        rows = table.find_all("tr")

        for row in rows[:3]:

            text = clean(
                row.get_text(
                    " ",
                    strip=True
                )
            ).lower()

            if (
                "rank" in text
                and "name" in text
                and "goals" in text
            ):
                return table

    return None


def extract_goalscorers(soup):
    found = {}

    # Start every tracked player at zero.
    for player, target in GOALSCORERS.items():

        found[player] = {
            "name": player,
            "goals": 0,
            "target": target,
            "on_target": False,
        }

    goals_table = find_goals_table(soup)

    if goals_table is None:

        raise RuntimeError(
            "Could not find the Premier League "
            "goalscorer table on BBC"
        )

    print(
        "Found Premier League goalscorer table"
    )

    for row in goals_table.find_all("tr"):

        cells = row.find_all(
            ["th", "td"]
        )

        if not cells:
            continue

        texts = [
            clean(
                cell.get_text(
                    " ",
                    strip=True
                )
            )
            for cell in cells
        ]

        row_text = " ".join(texts)

        if not row_text:
            continue

        matched_player = None

        for player in GOALSCORERS:

            if (
                player.lower()
                in row_text.lower()
            ):

                matched_player = player
                break

        if not matched_player:
            continue

        # The BBC row starts with the player's ranking.
        #
        # The second number is the goals total.
        numbers = re.findall(
            r"(?<![\d.])\d+(?![\d.])",
            row_text
        )

        if len(numbers) < 2:

            print(
                f"Could not determine goals for "
                f"{matched_player}: {row_text}"
            )

            continue

        try:
            goals = int(numbers[1])

        except ValueError:
            continue

        target = GOALSCORERS[
            matched_player
        ]

        found[matched_player] = {
            "name": matched_player,
            "goals": goals,
            "target": target,
            "on_target": goals >= target,
        }

        print(
            f"Matched goalscorer "
            f"{matched_player}: "
            f"{goals} goals"
        )

    # Report players who were not found.
    for player in GOALSCORERS:

        if found[player]["goals"] == 0:

            print(
                f"{player} was not found on the "
                f"goalscorer list - assuming 0 goals"
            )

    return found


# =============================================================
# MAIN
# =============================================================

def main():

    # ---------------------------------------------------------
    # LEAGUE TABLES
    # ---------------------------------------------------------

    print("Downloading BBC league tables...")

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

    # ---------------------------------------------------------
    # CHECK THAT EVERY REQUIRED TEAM WAS FOUND
    # ---------------------------------------------------------

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

    print(
        f"Successfully found all "
        f"{len(TEAMS)} tracked teams"
    )

    # ---------------------------------------------------------
    # PREMIER LEAGUE GOALSCORERS
    # ---------------------------------------------------------

    print(
        "Downloading Premier League goalscorers..."
    )

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

    scorers = extract_goalscorers(
        scorer_soup
    )

    # ---------------------------------------------------------
    # BUILD DATA
    # ---------------------------------------------------------

    payload = {
        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": TABLES_URL,

        "scorers_source": SCORERS_URL,

        "teams": [],

        "goalscorers": list(
            scorers.values()
        ),
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
        json.dumps(
            payload,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "Successfully generated data.json"
    )

    print(
        json.dumps(
            payload,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
