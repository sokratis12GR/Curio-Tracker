from collections import defaultdict


def rows_to_nested_json(rows: list[dict]) -> dict:
    nested = {
        "RewardTypes": {
            "1": "Trinket",
            "2": "Replacement",
            "3": "Replica",
            "4": "Experimented Base Type",
            "5": "Weapon Enchantment",
            "6": "Armor Enchantment",
            "7": "Scarab",
            "8": "Currency"
        },
        "Players": []
    }

    for row in rows:
        player_name = row["Logged By"].split("#")[0]
        league_name = row["League"]
        blueprint_name = row["Blueprint Type"]
        area_level = row["Area Level"]
        timestamp = row.get("Time", "")
        picked = row.get("Picked", False)
        stack_size = row.get("Stack Size", "")

        # Determine reward and type
        reward_name = ""
        type_id = 0
        for key, reward_type in nested["RewardTypes"].items():
            if row.get(reward_type):
                reward_name = row[reward_type]
                type_id = int(key)
                break

        if not reward_name:
            continue

        reward_entry = {
            "Record": str(row["Record #"]),
            "Reward": reward_name,
            "TypeId": type_id,
            "Timestamp": timestamp,
            "Picked": picked
        }
        if stack_size:
            reward_entry["StackSize"] = stack_size

        # Find or create player
        player = next((p for p in nested["Players"] if p["Player"] == player_name), None)
        if not player:
            player = {"Player": player_name, "Leagues": []}
            nested["Players"].append(player)

        # Find or create league
        league = next((l for l in player["Leagues"] if l["League"] == league_name), None)
        if not league:
            league = {"League": league_name, "Blueprints": []}
            player["Leagues"].append(league)

        # Find or create blueprint
        blueprint = next((b for b in league["Blueprints"] if b["Blueprint"] == blueprint_name), None)
        if not blueprint:
            blueprint = {
                "Blueprint": blueprint_name,
                "AreaLevel": area_level,
                "Rewards": []
            }
            league["Blueprints"].append(blueprint)

        blueprint["Rewards"].append(reward_entry)

    return nested


def nested_json_to_rows(nested: dict) -> list[dict]:
    rows = []

    for player in nested.get("Players", []):
        player_name = player["Player"]
        for league in player.get("Leagues", []):
            league_name = league["League"]
            for blueprint in league.get("Blueprints", []):
                blueprint_name = blueprint["Blueprint"]
                area_level = blueprint.get("AreaLevel", "")

                for reward in blueprint.get("Rewards", []):
                    row = {
                        "Record #": reward.get("Record", ""),
                        "Logged By": player_name,
                        "League": league_name,
                        "Blueprint Type": blueprint_name,
                        "Area Level": area_level,
                        "Time": reward.get("Timestamp", ""),
                        "Picked": reward.get("Picked", False),
                        "Stack Size": reward.get("StackSize", "")
                    }

                    # Map TypeId back to reward type column
                    type_id = str(reward.get("TypeId", ""))
                    reward_type = nested.get("RewardTypes", {}).get(type_id)
                    if reward_type:
                        row[reward_type] = reward.get("Reward", "")

                    rows.append(row)

    return rows
