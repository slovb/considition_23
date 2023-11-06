import os
import json
from scoring import calculateScore
from api import getGeneralData, getMapData, submit
from data_keys import (
    MapNames as MN,
    LocationKeys as LK,
    ScoringKeys as SK,
)
from dotenv import load_dotenv

load_dotenv()
apiKey = os.environ["apiKey"]
game_folder = "my_games"
log_folder = "log"
cache_folder = "cache"


def solve(mapEntity, generalData):
    solution = {LK.locations: {}}

    for key in mapEntity[LK.locations]:
        location = mapEntity[LK.locations][key]
        name = location[LK.locationName]

        salesVolume = location[LK.salesVolume]
        # print(salesVolume)
        # upper_lim = 120
        # lower_lim = 14
        # max_num = 5
        # if salesVolume > lower_lim:
        #     f9100Count = int(min(max_num, salesVolume // upper_lim))
        #     remainder = salesVolume - f9100Count * upper_lim
        #     f3100Count = int(min(max_num, remainder // lower_lim))
        #     solution[LK.locations][name] = {
        #         LK.f9100Count: f9100Count,
        #         LK.f3100Count: f3100Count,
        #     }
        cost = 14
        max_num = 5
        if salesVolume > cost:
            f3100Count = int(salesVolume // cost)
            f9100Count = 0
            while f3100Count > 4 and f9100Count < max_num:
                f9100Count += 1
                f3100Count -= 6
            f3100Count = max(0, min(5, f3100Count))
            f9100Count = min(5, f9100Count)
            solution[LK.locations][name] = {
                LK.f9100Count: f9100Count,
                LK.f3100Count: f3100Count,
            }
    return solution


def store(mapName, score):
    id_ = score[SK.gameId]

    # Store solution locally for visualization
    with open(f"{game_folder}\{id_}.json", "w", encoding="utf8") as f:
        json.dump(score, f, indent=4)
    # Log solution for easier management
    with open(f'{log_folder}/{mapName}.txt', 'a', encoding='utf8') as f:
        total = int(score[SK.gameScore][SK.total])
        f.write(f'{total} {id_}\n')


def main(mapName = None):
    for folder in [game_folder, log_folder, cache_folder]:
        if not os.path.exists(folder):
            print(f"Creating folder {folder}")
            os.makedirs(folder)    

    try:
        apiKey = os.environ["apiKey"]
    except Exception as e:
        raise SystemExit("Did you forget to create a .env file with the apiKey?")

    if not mapName:
        # User selct a map name
        print(f"1: {MN.stockholm}")
        print(f"2: {MN.goteborg}")
        print(f"3: {MN.malmo}")
        print(f"4: {MN.uppsala}")
        print(f"5: {MN.vasteras}")
        print(f"6: {MN.orebro}")
        print(f"7: {MN.london}")
        print(f"8: {MN.berlin}")
        print(f"9: {MN.linkoping}")
        option_ = input("Select the map you wish to play: ")

        match option_:
            case "1":
                mapName = MN.stockholm
            case "2":
                mapName = MN.goteborg
            case "3":
                mapName = MN.malmo
            case "4":
                mapName = MN.uppsala
            case "5":
                mapName = MN.vasteras
            case "6":
                mapName = MN.orebro
            case "7":
                mapName = MN.london
            case "8":
                mapName = MN.berlin
            case "9":
                mapName = MN.linkoping
            case _:
                print("Invalid choice.")

    if mapName:
        ##Get map data from Considition endpoint
        mapEntity = getMapData(mapName, apiKey, cache_folder)
        ##Get non map specific data from Considition endpoint
        generalData = getGeneralData(cache_folder)

        if mapEntity and generalData:
            solution = solve(mapEntity, generalData)

            # Score solution locally
            score = calculateScore(mapName, solution, mapEntity, generalData)
            total = score[SK.gameScore][SK.total]

            # Store
            id_ = score[SK.gameId]
            formatted_total = '{:,}'.format(int(total)).replace(',', ' ')
            print(f'{formatted_total}\t{id_}')
            store(mapName, score)
            


if __name__ == "__main__":
    main()
