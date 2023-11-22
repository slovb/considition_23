import os
import sys
import json
from typing import Dict
import api
from dotenv import load_dotenv

from data_keys import (
    LocationKeys as LK,
    ScoringKeys as SK,
    MapNames as MN,
    CoordinateKeys as CK,
)
from settings import Settings


load_dotenv()
apiKey = os.environ["apiKey"]


def load_game(id: str) -> Dict:
    with open(f"{Settings.game_folder}/{id}.json", "r", encoding="utf8") as f:
        return json.load(f)


def get_solution(game: Dict) -> Dict[str, Dict]:
    locations = {}
    mapName = game[SK.mapName]

    for k, v in game[LK.locations].items():
        if mapName not in [MN.gSandbox, MN.sSandbox]:
            if v[LK.f3100Count] == 0 and v[LK.f9100Count] == 0:
                continue
        locations[k] = {
            LK.f3100Count: v[LK.f3100Count],
            LK.f9100Count: v[LK.f9100Count],
        }
        if mapName in [MN.gSandbox, MN.sSandbox]:
            locations[k][LK.locationType] = v[LK.locationType]
            locations[k][CK.latitude] = v[CK.latitude]
            locations[k][CK.longitude] = v[CK.longitude]

    return {LK.locations: locations}


def submit(id: str) -> None:
    game = load_game(id)
    mapName = game[SK.mapName]
    solution = get_solution(game)
    print(f"Submitting solution to Considtion 2023\n")
    scoredSolution = api.submit(mapName, solution, apiKey)
    if scoredSolution:
        print("Successfully submitted game")
        game_id = scoredSolution[SK.gameId]
        print(f"id: {scoredSolution[SK.gameId]}")
        print(f"Score: {json.dumps(scoredSolution[SK.gameScore], indent=4)}")
        total = scoredSolution[SK.gameScore][SK.total]
        print("Total: {:,}".format(int(total)))
        log_file = f"{Settings.log_folder}/submit.txt"
        with open(log_file, "a", encoding="utf8") as f:
            f.write(f"{mapName} {total} {id} {game_id}\n")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        submit(sys.argv[1])
    else:
        print("Wrong number of arguments")
