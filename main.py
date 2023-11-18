import os
from multiprocessing import Pool
from dotenv import load_dotenv

from api import getGeneralData, getMapData
from data_keys import (
    MapNames as MN,
    LocationKeys as LK,
    ScoringKeys as SK,
)

from helper import apply_change, bundle
from settings import Settings
from store import store
from solver import Solver


load_dotenv()
apiKey = os.environ["apiKey"]


def starting_point(mapEntity, generalData):
    solution = {LK.locations: {}}

    for key in mapEntity[LK.locations]:
        location = mapEntity[LK.locations][key]
        name = location[LK.locationName]
        solution[LK.locations][name] = bundle(1, 0)
    return solution


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

            calculator = Solver(mapName, best_solution, mapEntity, generalData)
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
                for change in calculator.generate_changes(ignore=the_ugly):
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
