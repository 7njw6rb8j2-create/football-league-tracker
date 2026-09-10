def extract_goalscorers(soup):
    found = {}

    # Start every tracked player at 0 goals.
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

            if not matched_player:
                continue

            # BBC scorer rows contain rank first, then duplicated Goals values.
            # The second integer is the goal total.
            numbers = re.findall(r"(?<![\d.])\d+(?![\d.])", row_text)

            if len(numbers) < 2:
                continue

            try:
                goals = int(numbers[1])
            except ValueError:
                continue

            found[matched_player] = {
                "name": matched_player,
                "goals": goals,
                "target": GOALSCORERS[matched_player],
                "on_target": goals >= GOALSCORERS[matched_player],
            }

            print(f"Matched goalscorer {matched_player}: {goals} goals")

    return found
