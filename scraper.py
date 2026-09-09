import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

URL = "https://www.bbc.co.uk/sport/football/tables"
OUT = Path("site/data.json")

# League is associated with each club so the display remains stable even if BBC changes headings.
TEAMS = {
    "Wrexham": {"league": "Championship", "target": 8},
    "Stockport County": {"league": "League One", "target": 6},
    "Chelsea": {"league": "Premier League", "target": 4},
    "Barnet": {"league": "League Two", "target": 7},
}
ALIASES = {"Stockport": "Stockport County"}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FootballLeagueTracker/1.0)"}

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def position_from_cells(cells, row_index):
    for cell in cells[:3]:
        text = clean(cell.get_text(" ", strip=True))
        if re.fullmatch(r"\d{1,2}", text):
            n = int(text)
            if 1 <= n <= 40:
                return n
    return row_index

def extract_rows(soup):
    found = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        data_index = 0
        for row in rows:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            texts = [clean(c.get_text(" ", strip=True)) for c in cells]
            joined = " | ".join(texts)
            matched = None
            for alias, canonical in {**{k:k for k in TEAMS}, **ALIASES}.items():
                if re.search(rf"\b{re.escape(alias)}\b", joined, re.I):
                    matched = canonical
                    break
            if not matched:
                continue
            data_index += 1
            pos = position_from_cells(cells, data_index)
            nums = [int(x) for x in re.findall(r"(?<!\d)\d+(?!\d)", joined)]
            # BBC normally exposes position, played, won, drawn, lost, GF, GA, GD, points.
            # Prefer the numeric cell immediately after the team name for points if available.
            points = "-"
            for text in reversed(texts):
                if re.fullmatch(r"\d+", text):
                    points = int(text)
                    break
            found[matched] = {"position": pos, "points": points}
    return found

def main():
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    found = extract_rows(soup)
    missing = [name for name in TEAMS if name not in found]
    if missing:
        raise RuntimeError("Could not find these teams on BBC tables: " + ", ".join(missing))

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": URL,
        "teams": []
    }
    for name, cfg in TEAMS.items():
        item = found[name]
        payload["teams"].append({
            "name": name,
            "league": cfg["league"],
            "target": cfg["target"],
            "position": item["position"],
            "points": item["points"],
        })
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
