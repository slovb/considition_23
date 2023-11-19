from multiprocessing import Pool

from data_keys import (
    CoordinateKeys as CK,
    LocationKeys as LK,
    GeneralKeys as GK,
    ScoringKeys as SK,
)
from helper import apply_change, bundle
from scoring import distanceBetweenPoint, calculateScore
from settings import Settings
from store import store


class RegularSolver:
    def __init__(self, mapName, mapEntity, generalData):
        self.mapName = mapName
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.distance_cache = {}
        self.best = 0
        self.best_id = None
        self.solution = {"locations": {}}

    def calculate(self, change):
        return calculateScore(
            self.mapName,
            self.solution,
            change,
            self.mapEntity,
            self.generalData,
            self.distance_cache,
        )

    def initialize(self):
        if Settings.starting_point == "func":
            self.solution = self.starting_point()

    def starting_point(self):
        from helper import bundle

        solution = {LK.locations: {}}

        for key in self.mapEntity[LK.locations]:
            location = self.mapEntity[LK.locations][key]
            name = location[LK.locationName]
            solution[LK.locations][name] = bundle(f3=1, f9=0)
        return solution

    def rebuild_cache(self):
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

    def generate_changes(self, ignore=set()):
        locations = self.solution[LK.locations]
        for key in (key for key in locations if key not in ignore):
            location = locations[key]
            f3Count = location[LK.f3100Count]
            f9Count = location[LK.f9100Count]
            if f3Count > 0:  # decrease f3100
                yield {key: bundle(-1, 0)}
            if f3Count > 0 and f9Count < Settings.max_stations:  # f3100 -> f9100
                yield {key: bundle(-1, 1)}
            if f3Count > 1 and f9Count < Settings.max_stations:  # 2 f3100 -> f9100
                yield {key: bundle(-2, 1)}
            if f9Count > 0 and f3Count < Settings.max_stations:  # f9100 -> f3100
                yield {key: bundle(1, -1)}
            if f3Count < Settings.max_stations:  # increase f3100
                yield {key: bundle(1, 0)}
        for key in (
            key for key in self.mapEntity[LK.locations] if key not in ignore
        ):  # try to add a missing location
            if key not in locations:
                yield {key: bundle(1, 0)}

    def generate_moves(self):
        locations = self.mapEntity[LK.locations]
        for main_key in locations:
            main_location = self.solution[LK.locations].get(main_key)
            if (
                main_location is not None
                and main_location[LK.f3100Count] == Settings.max_stations
                and main_location[LK.f9100Count] == Settings.max_stations
            ):
                continue
            nearby = [
                key
                for key in self.distance_cache.get(main_key)
                if key in self.solution[LK.locations]
            ]
            for sub_key in nearby:
                sub_loc = self.solution[LK.locations].get(sub_key)
                changes = []
                if (
                    main_location is None
                    or main_location[LK.f3100Count] < Settings.max_stations
                ):
                    changes.append({main_key: bundle(1, 0)})
                if (
                    main_location is None
                    or main_location[LK.f9100Count] < Settings.max_stations
                ):
                    changes.append({main_key: bundle(0, 1)})
                if (
                    main_location is not None
                    and main_location[LK.f3100Count] > 0
                    and main_location[LK.f9100Count] < Settings.max_stations
                ):
                    changes.append({main_key: bundle(-1, 1)})
                for change in changes:
                    if (
                        main_location is None
                        or main_location[LK.f3100Count] < Settings.max_stations
                    ):
                        change[main_key] = bundle(1, 0)
                    elif main_location[LK.f3100Count] == Settings.max_stations:
                        change[main_key] = bundle(-1, 1)

                    if sub_loc[LK.f3100Count] == 0:
                        change[sub_key] = bundle(1, -1)
                    else:
                        change[sub_key] = bundle(-1, 0)
                    yield change

    def generate_consolidation(self):
        locations = self.mapEntity[LK.locations]
        for main_key in locations:
            main_location = self.solution[LK.locations].get(main_key)
            if (
                main_location is not None
                and main_location[LK.f3100Count] == Settings.max_stations
                and main_location[LK.f9100Count] == Settings.max_stations
            ):
                continue
            nearby = [
                key
                for key in self.distance_cache.get(main_key)
                if key in self.solution[LK.locations]
            ]
            if len(nearby) < 2:
                continue
            for i, sub_1_key in enumerate(nearby[:-1]):
                sub_1_loc = self.solution[LK.locations].get(sub_1_key)
                for sub_2_key in nearby[i + 1 :]:
                    sub_2_loc = self.solution[LK.locations].get(sub_2_key)
                    changes = []
                    if (
                        main_location is None
                        or main_location[LK.f3100Count] < Settings.max_stations
                    ):
                        changes.append({main_key: bundle(1, 0)})
                    if (
                        main_location is None
                        or main_location[LK.f9100Count] < Settings.max_stations
                    ):
                        changes.append({main_key: bundle(0, 1)})
                    if (
                        main_location is not None
                        and main_location[LK.f3100Count] > 0
                        and main_location[LK.f9100Count] < Settings.max_stations
                    ):
                        changes.append({main_key: bundle(-1, 1)})
                    for change in changes:
                        if sub_1_loc[LK.f3100Count] == 0:
                            change[sub_1_key] = bundle(1, -1)
                        else:
                            change[sub_1_key] = bundle(-1, 0)

                        if sub_2_loc[LK.f3100Count] == 0:
                            change[sub_2_key] = bundle(1, -1)
                        else:
                            change[sub_2_key] = bundle(-1, 0)
                        yield change

    def solve(self):
        if Settings.starting_point == "func":
            score = self.calculate(self.solution)
            self.best = score[SK.gameScore][SK.total]
            self.best_id = score[SK.gameId]

        the_good = set()
        the_bad = set()
        the_ugly = set()

        do_mega = Settings.do_mega
        mega_count = Settings.mega_count
        do_sets = Settings.do_sets

        stale_progress = False

        while True:
            if do_sets:
                the_ugly = the_bad.difference(the_good)  # these will be ignored
                the_good = set()
            else:
                the_ugly = set()

            # generate a set of changes
            changes = []
            for change in self.generate_changes(ignore=the_ugly):
                changes.append(change)
            if stale_progress:
                for change in self.generate_moves():
                    changes.append(change)
                for change in self.generate_consolidation():
                    changes.append(change)

            # score changes
            if Settings.do_multiprocessing:
                with Pool(4) as pool:
                    scores = pool.map(self.calculate, changes)
            else:
                scores = list(map(self.calculate, changes))

            # process scores, extract ids that improved and total scores
            improvements = []
            totals = []
            for i, score in enumerate(scores):
                total = score[SK.gameScore][SK.total]
                if total > self.best:  # improved total
                    improvements.append(i)
                    if do_sets:
                        for key in changes[i]:
                            the_good.add(key)
                elif do_sets:  # not improved total
                    for key in changes[i]:
                        the_bad.add(key)
                totals.append(total)

            if (
                do_mega and mega_count > 0
            ):  # do a megamerge a few times, merging all improvements
                megachange = {}
                # for i in sorted(improvements, key=lambda x: totals[x], reverse=True)[:len(improvements) // 2]:
                for i in improvements:
                    apply_change(megachange, changes[i], capped=False)
                changes.append(megachange)
                megascore = self.calculate(megachange)
                scores.append(megascore)
                totals.append(megascore[SK.gameScore][SK.total])

            if len(totals) == 0:  # safety check if too much ignoring has happened
                if do_sets:
                    do_sets = False
                    continue
                else:
                    break

            if (
                Settings.do_groups and len(improvements) > 2
            ):  # apply the group_size highest improvements that don't interact
                group_change = {}
                picked = set()
                pick_count = 0
                for i in sorted(
                    improvements, key=lambda x: totals[x], reverse=True
                ):  # the indexes of the group_size highest totals
                    if any([key in picked for key in changes[i]]):
                        continue
                    for key in changes[i]:
                        picked.add(key)
                        pick_count += 1
                        for nkey, distance in self.distance_cache[key].items():
                            if distance < Settings.groups_distance_limit:
                                picked.add(nkey)  # don't need nearby
                    apply_change(group_change, changes[i], capped=False)
                    if pick_count >= Settings.group_size:
                        break
                changes.append(group_change)
                group_score = self.calculate(group_change)
                scores.append(group_score)
                totals.append(group_score[SK.gameScore][SK.total])

            # apply the best change
            total = max(totals)
            if total > self.best:
                self.best = total
                index = totals.index(total)
                score = scores[index]
                self.best_id = score[SK.gameId]
                apply_change(self.solution[LK.locations], changes[index])
                store(self.mapName, score)
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
