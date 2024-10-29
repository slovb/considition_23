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
from helper import build_distance_cache
from map_limiter import MapLimiter
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
    mapLimiter: MapLimiter,
    sandbox_names: Dict[str, str],
    hotspot_footfall_cache: Dict,
) -> Dict:
    max_step_factor = 0.001
    step_lat = mapLimiter.latitudeDiff * max_step_factor * 2 * (random.random() - 0.5)
    step_long = mapLimiter.longitudeDiff * max_step_factor * 2 * (random.random() - 0.5)
    key = random.choice(list(solution[LK.locations].keys()))
    location = solution[LK.locations][key]
    location[CK.latitude] = mapLimiter.latitude(location[CK.latitude] + step_lat)
    location[CK.longitude] = mapLimiter.longitude(location[CK.longitude] + step_long)
    distance_cache = build_distance_cache(solution[LK.locations], generalData)
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


def jiggle_regular(
    mapName: str,
    solution: Dict,
    mapEntity: Dict,
    generalData: Dict,
    distance_cache: Dict[str, Dict],
) -> Dict:
    coin_toss = random.random()
    if coin_toss <= 0.4:
        key = random.choice(list(solution[LK.locations].keys()))
    else:
        key = random.choice(list(mapEntity[LK.locations].keys()))

    if key not in solution[LK.locations]:
        solution[LK.locations][key] = {
            LK.f3100Count: 0,
            LK.f9100Count: 0,
        }
    location = solution[LK.locations][key]

    if coin_toss > 0.4:
        increase(location)
    else:
        decrease(location)
        if location[LK.f3100Count] == location[LK.f9100Count] == 0:
            del solution[LK.locations][key]
    return calculateScore(
        mapName, solution, {}, mapEntity, generalData, distance_cache, round_total=False
    )


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
    solution = get_solution(load_game(id))

    if mapName in [MN.gSandbox, MN.sSandbox]:
        sandbox_names = {key: key for key in solution[LK.locations].keys()}
        hotspot_footfall_cache: Dict = {}
    else:
        distance_cache = build_distance_cache(mapEntity[LK.locations], generalData)

    while True:
        if mapName in [MN.gSandbox, MN.sSandbox]:
            score = jiggle_sandbox(
                mapName,
                solution,
                mapEntity,
                generalData,
                mapLimiter,
                sandbox_names,
                hotspot_footfall_cache,
            )
        else:
            score = jiggle_regular(
                mapName, solution, mapEntity, generalData, distance_cache
            )

        new_total = get_total(score)
        if new_total > total:
            print("")
            store(mapName, score)
            total = new_total
        elif abs(new_total - total) < 16.0:
            # print("+", end="", flush=True)
            pass
        else:
            # print("_", end="", flush=True)
            total, new_id = best(mapName)
            if id != new_id:
                print(total)
                id = new_id
            solution = get_solution(load_game(id))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        jiggle(sys.argv[1])
    else:
        print("Wrong number of arguments")
