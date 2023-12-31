import os
import random
import sys
from typing import Dict
from data_keys import (
    MapNames as MN,
    MapKeys as MK,
    LocationKeys as LK,
    CoordinateKeys as CK,
)
from dotenv import load_dotenv
from api import getGeneralData, getMapData
from map_limiter import MapLimiter
from original_scoring import calculateScore

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
    mapLimiter: MapLimiter,
) -> Dict:
    max_step_factor = 0.001
    step_lat = mapLimiter.latitudeDiff * max_step_factor * 2 * (random.random() - 0.5)
    step_long = mapLimiter.longitudeDiff * max_step_factor * 2 * (random.random() - 0.5)
    location = random.choice(list(solution[LK.locations].values()))
    location[CK.latitude] = mapLimiter.latitude(location[CK.latitude] + step_lat)
    location[CK.longitude] = mapLimiter.longitude(location[CK.longitude] + step_long)
    return calculateScore(mapName, solution, mapEntity, generalData, round_total=True)


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


def jiggle_regular(
    mapName: str, solution: Dict, mapEntity: Dict, generalData: Dict
) -> Dict:
    key = random.choice(list(solution[LK.locations].keys()))
    location = solution[LK.locations][key]
    if random.random() > 0.4:
        increase(location)
    else:
        decrease(location)
        if location[LK.f3100Count] == location[LK.f9100Count] == 0:
            del solution[LK.locations][key]
    return calculateScore(mapName, solution, mapEntity, generalData, round_total=True)


def jiggle(mapName: str) -> None:
    mapEntity = getMapData(mapName, apiKey, Settings.cache_folder)
    generalData = getGeneralData(Settings.cache_folder)
    if not mapEntity or not generalData:
        raise SystemError("Unable to load map and general data")
    if mapName in [MN.gSandbox, MN.sSandbox]:
        mapLimiter = MapLimiter(
            latitudeMin=mapEntity[MK.border][MK.latitudeMin],
            latitudeMax=mapEntity[MK.border][MK.latitudeMax],
            longitudeMin=mapEntity[MK.border][MK.longitudeMin],
            longitudeMax=mapEntity[MK.border][MK.longitudeMax],
        )

    total, id = best(mapName)
    print(f"{total}\t\t{id}")

    while True:
        total, id = best(mapName)
        game = load_game(id)
        solution = get_solution(game)

        while True:
            if mapName in [MN.gSandbox, MN.sSandbox]:
                score = jiggle_sandbox(
                    mapName, solution, mapEntity, generalData, mapLimiter
                )
            else:
                score = jiggle_regular(mapName, solution, mapEntity, generalData)

            new_total = get_total(score)
            if new_total > total:
                print("")
                store(mapName, score)
                total = new_total
            elif abs(new_total - total) < 16.0:
                print("+", end="", flush=True)
            else:
                print("_", end="", flush=True)
                break


if __name__ == "__main__":
    if len(sys.argv) == 2:
        jiggle(sys.argv[1])
    else:
        print("Wrong number of arguments")
