from typing import Dict
from data_keys import ScoringKeys as SK
import json

from settings import Settings


def store(mapName: str, score: Dict) -> None:
    id_ = score[SK.gameId]
    total = score[SK.gameScore][SK.total]
    formatted_total = "{:,}".format(int(total)).replace(",", " ")
    print(f"{formatted_total}\t\t{id_}")

    # Store solution locally for visualization
    with open(f"{Settings.game_folder}\{id_}.json", "w", encoding="utf8") as f:
        json.dump(score, f, indent=4)
    # Log solution for easier management
    with open(f"{Settings.log_folder}/{mapName}.txt", "a", encoding="utf8") as f:
        total = int(score[SK.gameScore][SK.total])
        f.write(f"{total} {id_}\n")
