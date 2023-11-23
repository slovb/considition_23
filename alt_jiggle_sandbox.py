import os
import random
import sys
from typing import Dict
from data_keys import (
    MapNames as MN,
    LocationKeys as LK,
)
from dotenv import load_dotenv
from api import getGeneralData, getMapData
from helper import build_distance_cache
from scoring import calculateScore

from settings import Settings
from best import best
from store import store
from submit import get_solution, load_game
from suggestion import get_total


load_dotenv()
apiKey = os.environ["apiKey"]


def jiggle_sandbox(
    mapName: str,
    solution: Dict,
    mapEntity: Dict,
    generalData: Dict,
    distance_cache: Dict[str, Dict],
    sandbox_names: Dict[str, str],
    hotspot_footfall_cache: Dict,
) -> Dict:
    key = random.choice(list(solution[LK.locations].keys()))
    location = solution[LK.locations][key]
    if random.random() > 0.4:
        increase(location)
    else:
        decrease(location)

    return calculateScore(
        mapName,
        solution,
        {},
        mapEntity,
        generalData,
        distance_cache,
        sandbox_names=sandbox_names,
        inverse_sandbox_names=sandbox_names,
        hotspot_footfall_cache=hotspot_footfall_cache,
        round_total=False,
    )


def increase(location):
    if location[LK.f3100Count] < Settings.max_stations:
        location[LK.f3100Count] += 1
    elif location[LK.f9100Count] < Settings.max_stations:
        location[LK.f3100Count] = 0
        location[LK.f9100Count] += 1


def decrease(location):
    if location[LK.f3100Count] > 0:
        location[LK.f3100Count] -= 1
    elif location[LK.f9100Count] > 0:
        location[LK.f9100Count] -= 1
        location[LK.f3100Count] = 2


def jiggle(mapName: str) -> None:
    mapEntity = getMapData(mapName, apiKey, Settings.cache_folder)
    generalData = getGeneralData(Settings.cache_folder)
    if not mapEntity or not generalData:
        raise SystemError("Unable to load map and general data")

    total, id = best(mapName)
    print(f"{total}\t\t{id}")
    game = load_game(id)
    solution = get_solution(game)

    if mapName in [MN.gSandbox, MN.sSandbox]:
        sandbox_names = {key: key for key in solution[LK.locations].keys()}
        hotspot_footfall_cache: Dict = {}
        distance_cache = build_distance_cache(solution[LK.locations], generalData)
    else:
        raise SystemError("WRONG PROGRAM FOR NOT SANDBOX")

    while True:
        score = jiggle_sandbox(
            mapName,
            solution,
            mapEntity,
            generalData,
            distance_cache,
            sandbox_names,
            hotspot_footfall_cache,
        )

        new_total = get_total(score)
        if new_total > total:
            print("")
            store(mapName, score)
            total = new_total
        elif abs(new_total - total) < 16.0:
            print("+", end="", flush=True)
        else:
            print("_", end="", flush=True)
            total, id = best(mapName)
            game = load_game(id)
            solution = get_solution(game)
            distance_cache = build_distance_cache(solution[LK.locations], generalData)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        jiggle(sys.argv[1])
    else:
        print("Wrong number of arguments")
