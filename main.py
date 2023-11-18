import os
import json
from scoring import distanceBetweenPoint, calculateScore
from api import getGeneralData, getMapData
from data_keys import (
    MapNames as MN,
    CoordinateKeys as CK,
    LocationKeys as LK,
    GeneralKeys as GK,
    ScoringKeys as SK,
    HotspotKeys as HK,
    GeneralKeys as GK,
    CoordinateKeys as CK,
)
from multiprocessing import Pool
from dotenv import load_dotenv
from settings import Settings

load_dotenv()
apiKey = os.environ["apiKey"]


class Calculator():
    def __init__(self, mapName, solution, mapEntity, generalData):
        self.mapName = mapName
        self.solution = solution
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.distance_cache = {}

    def calculate(self, change):
        return calculateScore(self.mapName, self.solution, change, self.mapEntity, self.generalData, self.distance_cache)
    
    def rebuild_distance_cache(self):
        locations = self.mapEntity[LK.locations]
        keys = []
        lats = []
        longs = []
        for key, location in locations.items():
            keys.append(key)
            self.distance_cache[key] = {}
            lats.append(location[CK.latitude])
            longs.append(location[CK.longitude])
        for i in range(len(lats) - 1):
            for j in range(i + 1, len(lats)):
                distance = distanceBetweenPoint(lats[i], longs[i], lats[j], longs[j])
                if distance < self.generalData[GK.willingnessToTravelInMeters]:
                    self.distance_cache[keys[i]][keys[j]] = distance
                    self.distance_cache[keys[j]][keys[i]] = distance

    def generate_moves(self):
        locations = self.mapEntity[LK.locations]
        for main_key in locations:
            main_location = self.solution[LK.locations].get(main_key)
            if main_location is not None and main_location[LK.f3100Count] == Settings.max_stations and main_location[LK.f9100Count] == Settings.max_stations:
                continue
            nearby = [key for key in self.distance_cache.get(main_key) if key in self.solution[LK.locations]]
            for sub_key in nearby:
                sub_loc = self.solution[LK.locations].get(sub_key)
                changes = []
                if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
                    changes.append(
                        {
                            main_key: {
                                LK.f3100Count: 1,
                                LK.f9100Count: 0,
                            }
                        }
                    )
                if main_location is None or main_location[LK.f9100Count] < Settings.max_stations:
                    changes.append(
                        {
                            main_key: {
                                LK.f3100Count: 0,
                                LK.f9100Count: 1,
                            }
                        }
                    )
                if main_location is not None and main_location[LK.f3100Count] > 0 and main_location[LK.f9100Count] < Settings.max_stations:
                    changes.append(
                        {
                            main_key: {
                                LK.f3100Count: -1,
                                LK.f9100Count: 1,
                            }
                        }
                    )
                for change in changes:
                    if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
                        change[main_key] = {
                            LK.f3100Count: 1,
                            LK.f9100Count: 0,
                        }
                    elif main_location[LK.f3100Count] == Settings.max_stations:
                        change[main_key] = {
                            LK.f3100Count: -1,
                            LK.f9100Count: 1,
                        }

                    if sub_loc[LK.f3100Count] == 0:
                        change[sub_key] = {
                            LK.f3100Count: 1,
                            LK.f9100Count: -1,
                        }
                    else:
                        change[sub_key] = {
                            LK.f3100Count: -1,
                            LK.f9100Count: 0,
                        }
                    yield change

    def generate_consolidation(self):
        locations = self.mapEntity[LK.locations]
        for main_key in locations:
            main_location = self.solution[LK.locations].get(main_key)
            if main_location is not None and main_location[LK.f3100Count] == Settings.max_stations and main_location[LK.f9100Count] == Settings.max_stations:
                continue
            nearby = [key for key in self.distance_cache.get(main_key) if key in self.solution[LK.locations]]
            if len(nearby) < 2:
                continue
            for i, sub_1_key in enumerate(nearby[:-1]):
                sub_1_loc = self.solution[LK.locations].get(sub_1_key)
                for sub_2_key in nearby[i+1:]:
                    sub_2_loc = self.solution[LK.locations].get(sub_2_key)
                    changes = []
                    if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
                        changes.append(
                            {
                                main_key: {
                                    LK.f3100Count: 1,
                                    LK.f9100Count: 0,
                                }
                            }
                        )
                    if main_location is None or main_location[LK.f9100Count] < Settings.max_stations:
                        changes.append(
                            {
                                main_key: {
                                    LK.f3100Count: 0,
                                    LK.f9100Count: 1,
                                }
                            }
                        )
                    if main_location is not None and main_location[LK.f3100Count] > 0 and main_location[LK.f9100Count] < Settings.max_stations:
                        changes.append(
                            {
                                main_key: {
                                    LK.f3100Count: -1,
                                    LK.f9100Count: 1,
                                }
                            }
                        )
                    for change in changes:
                        if sub_1_loc[LK.f3100Count] == 0:
                            change[sub_1_key] = {
                                LK.f3100Count: 1,
                                LK.f9100Count: -1,
                            }
                        else:
                            change[sub_1_key] = {
                                LK.f3100Count: -1,
                                LK.f9100Count: 0,
                            }

                        if sub_2_loc[LK.f3100Count] == 0:
                            change[sub_2_key] = {
                                LK.f3100Count: 1,
                                LK.f9100Count: -1,
                            }
                        else:
                            change[sub_2_key] = {
                                LK.f3100Count: -1,
                                LK.f9100Count: 0,
                            }
                        yield change


def starting_point(mapEntity, generalData):
    solution = {LK.locations: {}}

    for key in mapEntity[LK.locations]:
        location = mapEntity[LK.locations][key]
        name = location[LK.locationName]
        solution[LK.locations][name] = {
            LK.f3100Count: 1,
            LK.f9100Count: 0,
        }


    # for key in mapEntity[LK.locations]:
    #     location = mapEntity[LK.locations][key]
    #     name = location[LK.locationName]

    #     salesVolume = location[LK.salesVolume]

    #     cost = 14
    #     if salesVolume > cost:
    #         f3100Count = int(salesVolume // cost)
    #         f9100Count = 0
    #         while f3100Count > Settings.max_stations-1 and f9100Count < Settings.max_stations:
    #             f9100Count += 1
    #             f3100Count -= 6
    #         f3100Count = max(0, min(Settings.max_stations, f3100Count))
    #         f9100Count = min(Settings.max_stations, f9100Count)
    #         solution[LK.locations][name] = {
    #             LK.f9100Count: f9100Count,
    #             LK.f3100Count: f3100Count,
    #         }
    return solution


def store(mapName, score):
    id_ = score[SK.gameId]
    total = score[SK.gameScore][SK.total]
    formatted_total = '{:,}'.format(int(total)).replace(',', ' ')
    print(f'{formatted_total}\t\t{id_}')

    # Store solution locally for visualization
    with open(f"{Settings.game_folder}\{id_}.json", "w", encoding="utf8") as f:
        json.dump(score, f, indent=4)
    # Log solution for easier management
    with open(f'{Settings.log_folder}/{mapName}.txt', 'a', encoding='utf8') as f:
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
        if locations[key][LK.f3100Count] > 0 and locations[key][LK.f9100Count] < Settings.max_stations: # f3100 -> f9100
            yield {
                key: {
                    LK.f3100Count: -1,
                    LK.f9100Count: 1,
                }
            }
        if locations[key][LK.f3100Count] > 1 and locations[key][LK.f9100Count] < Settings.max_stations: # 2 f3100 -> f9100
            yield {
                key: {
                    LK.f3100Count: -2,
                    LK.f9100Count: 1,
                }
            }
        if locations[key][LK.f9100Count] > 0 and locations[key][LK.f3100Count] < Settings.max_stations: # f9100 -> f3100
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: -1,
                }
            }
        if locations[key][LK.f3100Count] < Settings.max_stations: # increase f3100
            yield {
                key: {
                    LK.f3100Count: 1,
                    LK.f9100Count: 0,
                }
            }
        # if locations[key][LK.f9100Count] < Settings.max_stations: # increase f9100
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
                if val < 0 or val > Settings.max_stations:
                    loc[key] = min(Settings.max_stations, max(0, val))


def main(mapName = None):
    for folder in [Settings.game_folder, Settings.log_folder, Settings.cache_folder]:
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
        print(f"10: {MN.sSandbox}")
        print(f"11: {MN.gSandbox}")
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
            case "10":
                mapName = MN.sSandbox
            case "11":
                mapName = MN.gSandbox
            case _:
                print("Invalid choice.")

    if mapName:
        ##Get map data from Considition endpoint
        mapEntity = getMapData(mapName, apiKey, Settings.cache_folder)
        ##Get non map specific data from Considition endpoint
        generalData = getGeneralData(Settings.cache_folder)

        if mapEntity and generalData:
            if Settings.starting_point == 'func':
                best_solution = starting_point(mapEntity, generalData)
            else:
                best_solution = {'locations': {}}

            calculator = Calculator(mapName, best_solution, mapEntity, generalData)
            calculator.rebuild_distance_cache()

            if Settings.starting_point == 'func':
                score = calculator.calculate(best_solution)
                best = score[SK.gameScore][SK.total]
                best_id = score[SK.gameId]
            else:
                best = 0
                best_id = None

            the_good = set()
            the_bad = set()
            the_ugly = set()

            do_mega = Settings.do_mega
            mega_count = Settings.mega_count
            do_sets = Settings.do_sets

            stale_progress = False

            while True:
                calculator.solution = best_solution

                if do_sets:
                    the_ugly = the_bad.difference(the_good) # these will be ignored
                    the_good = set()
                else:
                    the_ugly = set()

                # generate a set of changes
                changes = []
                for change in generate_changes(best_solution[LK.locations], mapEntity, ignore=the_ugly):
                    changes.append(change)
                if stale_progress:
                    for change in calculator.generate_moves():
                        changes.append(change)
                    for change in calculator.generate_consolidation():
                        changes.append(change)

                # score changes
                if Settings.do_multiprocessing:
                    with Pool(4) as pool:
                        scores = pool.map(calculator.calculate, changes)
                else:
                    scores = list(map(calculator.calculate, changes))
                
                # process scores, extract ids that improved and total scores
                improvements = []
                totals = []
                for i, score in enumerate(scores):
                    total = score[SK.gameScore][SK.total]
                    if total > best: # improved total
                        improvements.append(i)
                        if do_sets:
                            for key in changes[i]:
                                the_good.add(key)
                    elif do_sets: # not improved total
                        for key in changes[i]:
                            the_bad.add(key)
                    totals.append(total)

                if do_mega and mega_count > 0: # do a megamerge a few times, merging all improvements
                    megachange = {}
                    # for i in sorted(improvements, key=lambda x: totals[x], reverse=True)[:len(improvements) // 2]:
                    for i in improvements:
                        apply_change(megachange, changes[i], capped=False)
                    changes.append(megachange)
                    megascore = calculator.calculate(megachange)
                    scores.append(megascore)
                    totals.append(megascore[SK.gameScore][SK.total])

                if len(totals) == 0: # safety check if too much ignoring has happened
                    if do_sets:
                        do_sets = False
                        continue
                    else:
                        break

                if Settings.do_groups and len(improvements) > 2: # apply the group_size highest improvements that don't intersect
                    group_change = {}
                    picked = set()
                    for i in sorted(improvements, key=lambda x: totals[x], reverse=True): # the indexes of the group_size highest totals
                        if any([key in picked for key in changes[i]]):
                            continue
                        for key in changes[i]:
                            picked.add(key)
                        apply_change(group_change, changes[i], capped=False)
                        if len(picked) >= Settings.group_size:
                            break
                    changes.append(group_change)
                    group_score = calculator.calculate(group_change)
                    scores.append(group_score)
                    totals.append(group_score[SK.gameScore][SK.total])

                # apply the best change
                total = max(totals)
                if total > best:
                    best = total
                    index = totals.index(total)
                    score = scores[index]
                    best_id = score[SK.gameId]
                    apply_change(best_solution[LK.locations], changes[index])
                    store(mapName, score)
                    stale_progress = False
                elif do_mega and mega_count > 0:
                    mega_count = 0
                elif do_sets:
                    do_sets = False
                elif not stale_progress:
                    stale_progress = True
                else:
                    break

                # post
                if do_mega and mega_count > 0:
                    mega_count -= 1

            formatted_best = '{:,}'.format(int(best)).replace(',', ' ')
            print(f'Best: {formatted_best}\t{best_id}')

if __name__ == "__main__":
    main()
