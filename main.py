import os
import json
from scoring import calculateScore
from api import getGeneralData, getMapData, submit
from data_keys import (
    MapNames as MN,
    LocationKeys as LK,
    ScoringKeys as SK,
)
# from multiprocessing import Pool
from dotenv import load_dotenv

load_dotenv()
apiKey = os.environ["apiKey"]
game_folder = "my_games"
log_folder = "log"
cache_folder = "cache"


class Calculator():
    def __init__(self, mapName, solution, mapEntity, generalData):
        self.mapName = mapName
        self.solution = solution
        self.mapEntity = mapEntity
        self.generalData = generalData

    def calculate(self, change):
        return calculateScore(self.mapName, self.solution, change, self.mapEntity, self.generalData)


def starting_point(mapEntity, generalData):
    solution = {LK.locations: {}}

    for key in mapEntity[LK.locations]:
        location = mapEntity[LK.locations][key]
        name = location[LK.locationName]

        salesVolume = location[LK.salesVolume]

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
    total = score[SK.gameScore][SK.total]
    formatted_total = '{:,}'.format(int(total)).replace(',', ' ')
    print(f'{formatted_total}\t\t{id_}')

    # Store solution locally for visualization
    with open(f"{game_folder}\{id_}.json", "w", encoding="utf8") as f:
        json.dump(score, f, indent=4)
    # Log solution for easier management
    with open(f'{log_folder}/{mapName}.txt', 'a', encoding='utf8') as f:
        total = int(score[SK.gameScore][SK.total])
        f.write(f'{total} {id_}\n')


def generate_changes(solution, mapEntity):
    for key in solution[LK.locations]:
        if solution[LK.locations][key][LK.f3100Count] > 0: # increase f3100
            yield {
                key: {
                    LK.f3100Count: -1,
                    LK.f9100Count: 0,
                }
            }
        if solution[LK.locations][key][LK.f9100Count] > 0: # decrease f9100
            yield {
                key: {
                    LK.f3100Count: 0,
                    LK.f9100Count: -1,
                }
            }
        if solution[LK.locations][key][LK.f3100Count] > 0 and solution[LK.locations][key][LK.f9100Count] < 5: # f3100 -> f9100
            yield {
                key: {
                    LK.f3100Count: -1,
                    LK.f9100Count: 1,
                }
            }
        if solution[LK.locations][key][LK.f3100Count] < 5: # increase f3100
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: 0,
                }
            }
    for key in mapEntity[LK.locations]: # try to add a missing location
        if key not in solution[LK.locations]:
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: 0,
                }
            }


def apply_change(solution, change):
    for key, mod in change.items():
        if key not in solution[LK.locations]:
            solution[LK.locations][key] = mod
        else:
            for mkey, mval in mod.items():
                solution[LK.locations][key][mkey] += mval
            if solution[LK.locations][key][LK.f3100Count] == 0 and solution[LK.locations][key][LK.f9100Count] == 0:
                del solution[LK.locations][key]
    return solution


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
            solution = starting_point(mapEntity, generalData)
            
            score = calculateScore(mapName, solution, {}, mapEntity, generalData)
            best = score[SK.gameScore][SK.total]
            best_id = score[SK.gameId]
            best_solution = solution

            while True:
                changes = []
                for change in generate_changes(best_solution, mapEntity):
                    changes.append(change)

                calculator = Calculator(mapName, best_solution, mapEntity, generalData)
                # with Pool(4) as pool:
                #     scores = pool.map(cc.calculate, changes)
                scores = list(map(calculator.calculate, changes))
                
                totals = []
                for score in scores:
                    total = score[SK.gameScore][SK.total]
                    totals.append(total)

                total = max(totals)
                if total > best:
                    best = total
                    index = totals.index(total)
                    score = scores[index]
                    best_id = score[SK.gameId]
                    best_solution = apply_change(best_solution, changes[index])
                    store(mapName, score)
                else:
                    break
            formatted_best = '{:,}'.format(int(best)).replace(',', ' ')
            print(f'Best: {formatted_best}\t{best_id}')

if __name__ == "__main__":
    main()
