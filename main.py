import os
import json
from scoring import calculateScore
from api import getGeneralData, getMapData
from data_keys import (
    MapNames as MN,
    LocationKeys as LK,
    ScoringKeys as SK,
)
from multiprocessing import Pool
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


def generate_changes(locations, mapEntity, ignore = set()):
    for key in (key for key in locations if key not in ignore):
        if locations[key][LK.f3100Count] > 0: # decrease f3100
            yield {
                key: {
                    LK.f3100Count: -1,
                    LK.f9100Count: 0,
                }
            }
        # if locations[key][LK.f9100Count] > 0: # decrease f9100
        #     yield {
        #         key: {
        #             LK.f3100Count: 0,
        #             LK.f9100Count: -1,
        #         }
        #     }
        if locations[key][LK.f3100Count] > 0 and locations[key][LK.f9100Count] < 5: # f3100 -> f9100
            yield {
                key: {
                    LK.f3100Count: -1,
                    LK.f9100Count: 1,
                }
            }
        if locations[key][LK.f9100Count] > 0 and locations[key][LK.f3100Count] < 5: # f9100 -> f3100
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: -1,
                }
            }
        if locations[key][LK.f3100Count] < 5: # increase f3100
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: 0,
                }
            }
        # if locations[key][LK.f9100Count] < 5: # increase f9100
        #     yield {
        #         key: {
        #             LK.f3100Count: 0,
        #             LK.f9100Count: 1,
        #         }
        #     }
    for key in (key for key in mapEntity[LK.locations] if key not in ignore): # try to add a missing location
        if key not in locations:
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: 0,
                }
            }
            # yield {
            #     key: {
            #         LK.f3100Count: 0,
            #         LK.f9100Count: 1,
            #     }
            # }


def apply_change(locations, change, capped=True):
    for key, mod in change.items():
        if key not in locations:
            locations[key] = mod
        else:
            for mkey, mval in mod.items():
                locations[key][mkey] = locations[key][mkey] + mval
            if locations[key][LK.f3100Count] == 0 and locations[key][LK.f9100Count] == 0:
                del locations[key]
    if capped:
        for loc in locations.values():
            for key, val in loc.items():
                if val < 0 or val > 5:
                    loc[key] = min(5, max(0, val))


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
            # solution = starting_point(mapEntity, generalData)
            # score = calculateScore(mapName, solution, {}, mapEntity, generalData)
            # best = score[SK.gameScore][SK.total]
            # best_id = score[SK.gameId]

            solution = {'locations': {}}
            best = 0
            best_id = None
            best_solution = solution

            the_good = set()
            the_bad = set()
            the_ugly = set()

            do_mega_start = True
            do_groups = True
            group_size = 16
            do_sets = True
            while True:
                if do_sets:
                    the_ugly = the_bad.difference(the_good)
                    the_good = set()
                else:
                    the_ugly = set()

                changes = []
                for change in generate_changes(best_solution[LK.locations], mapEntity, ignore = the_ugly):
                    changes.append(change)

                calculator = Calculator(mapName, best_solution, mapEntity, generalData)
                with Pool(8) as pool:
                    scores = pool.map(calculator.calculate, changes)
                # scores = list(map(calculator.calculate, changes))
                
                improvements = []
                totals = []
                for i, score in enumerate(scores):
                    total = score[SK.gameScore][SK.total]
                    if total > best:
                        improvements.append(i)
                        if do_sets:
                            for key in changes[i]:
                                the_good.add(key)
                    elif do_sets:
                        for key in changes[i]:
                            the_bad.add(key)
                    totals.append(total)
                
                if do_mega_start: # do a megamerge once
                    megachange = {}
                    for i in improvements:
                        apply_change(megachange, changes[i], capped=False)
                    changes.append(megachange)
                    megascore = calculator.calculate(megachange)
                    scores.append(megascore)
                    totals.append(megascore[SK.gameScore][SK.total])
                    do_mega_start = False

                if len(totals) == 0: # safety 
                    if do_sets:
                        do_sets = False
                        continue
                    else:
                        break

                if do_groups and len(improvements) > 2: # apply the group_size highest improvements that don't intersect
                    group_change = {}
                    picked = set()
                    for i in sorted(improvements, key=lambda x: totals[x], reverse=True): # the indexes of the group_size highest totals
                        if any([key in picked for key in changes[i]]):
                            continue
                        for key in changes[i]:
                            picked.add(key)
                        apply_change(group_change, changes[i], capped=False)
                        if len(picked) >= group_size:
                            break
                    changes.append(group_change)
                    group_score = calculator.calculate(group_change)
                    scores.append(group_score)
                    totals.append(group_score[SK.gameScore][SK.total])

                # apply the best
                total = max(totals)
                if total > best:
                    best = total
                    index = totals.index(total)
                    score = scores[index]
                    best_id = score[SK.gameId]
                    apply_change(best_solution[LK.locations], changes[index])
                    store(mapName, score)
                elif do_sets:
                    do_sets = False
                else:
                    break
            formatted_best = '{:,}'.format(int(best)).replace(',', ' ')
            print(f'Best: {formatted_best}\t{best_id}')

if __name__ == "__main__":
    main()
