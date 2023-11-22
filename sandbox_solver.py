import json
from multiprocessing import Pool

from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    LocationKeys as LK,
    MapKeys as MK,
    ScoringKeys as SK,
)
from helper import apply_change, bundle
from map_limiter import MapLimiter
from sandbox_helper import build_hotspot_cache, find_possible_locations, temporary_names
from scoring import calculateScore
from original_scoring import calculateScore as originalCalculateScore
from settings import Settings, KW
from solver import Solver
from store import store


class SandboxSolver(Solver):
    def __init__(self, mapName, mapEntity, generalData):
        super().__init__(mapName=mapName, mapEntity=mapEntity, generalData=generalData)

        self.hotspot_cache = {}
        self.possible_locations = {}
        self.no_remove = False

    def calculate(self, change, skip_validation=True):
        names, inverse = temporary_names(self.solution, change)
        return calculateScore(
            self.mapName,
            self.solution,
            change,
            self.mapEntity,
            self.generalData,
            self.distance_cache,
            names,
            inverse,
            skip_validation=skip_validation,
        )

    def calculate_verification(self):
        solution = {LK.locations: {}}
        fields = [
            LK.f3100Count,
            LK.f9100Count,
            CK.latitude,
            CK.longitude,
            LK.locationType,
        ]
        i = 1
        for location in self.solution[LK.locations].values():
            solution[LK.locations][f"location{i}"] = {
                field: location[field] for field in fields
            }
            i += 1
        return originalCalculateScore(
            self.mapName, solution, self.mapEntity, self.generalData
        )

    def initialize(self):
        super().initialize()
        self.map_limiter = MapLimiter(
            latitudeMin=self.mapEntity[MK.border][MK.latitudeMin],
            latitudeMax=self.mapEntity[MK.border][MK.latitudeMax],
            longitudeMin=self.mapEntity[MK.border][MK.longitudeMin],
            longitudeMax=self.mapEntity[MK.border][MK.longitudeMax],
        )
        self.update_limits()
        self.rebuild_cache()

    def rebuild_cache(self):
        self.hotspot_cache = build_hotspot_cache(
            mapEntity=self.mapEntity, generalData=self.generalData
        )
        self.possible_locations = find_possible_locations(
            hotspot_cache=self.hotspot_cache, map_limiter=self.map_limiter
        )
        self.rebuild_distance_cache(self.possible_locations)

    def find_candidates(self):
        return self.find_new_locations()

    def find_new_locations(self):
        changes = []
        remaining_types = self.remaining_types_in_order()
        if len(remaining_types) == 0:
            return []
        elif len(remaining_types) == 1:
            # get those last kiosks
            self.no_remove = True
        print(self.limits)

        # try to add locations
        for change in self.generate_additions(ignore=self.the_ugly):
            changes.append(change)

        return changes

    def improve_scored_candidates(self, candidates, totals, scores):
        remaining_types = self.remaining_types_in_order()
        # try adjustments of the best additions
        suggestions = []
        adjust_how_many = Settings.sandbox_explore_how_many
        if adjust_how_many > 0:
            for i in sorted(
                range(len(candidates)), key=lambda x: totals[x], reverse=True
            ):
                change = candidates[i]
                for type in remaining_types:
                    for f_count in [(1, 0), (0, 1), (1, 1)]:
                        suggestion = {}
                        for loc_key, location in change.items():
                            if (
                                type == location[LK.locationType]
                                and f_count[0] == location[LK.f3100Count]
                                and f_count[1] == location[LK.f9100Count]
                            ):  # no repeats
                                continue
                            suggestion[loc_key] = bundle(
                                latitude=location[CK.latitude],
                                longitude=location[CK.longitude],
                                type=type,
                                f3=f_count[0],
                                f9=f_count[1],
                            )
                        suggestions.append(suggestion)
                adjust_how_many -= 1
                if adjust_how_many <= 0:
                    break
        return suggestions

    def another_improve_scored_candidates(self, candidates, totals, scores):
        suggestions = []
        if (
            Settings.do_sandbox_groups
        ):  # apply the group_size highest improvements that don't intersect or are nearby
            group_change = {}
            picked = set()
            pick_count = 0
            counts = {key: 0 for key in self.limits}
            for i in sorted(
                range(len(candidates)), key=lambda x: totals[x], reverse=True
            ):
                # looping through the indexes of the highest totals
                if any([key in picked for key in candidates[i]]):
                    continue
                too_much = False
                for type, count in counts.items():
                    add = len(
                        [
                            key
                            for key, location in candidates[i].items()
                            if location[LK.locationType] == type
                        ]
                    )
                    if add + count >= self.limits[type]:
                        too_much = True
                        break
                if too_much:
                    continue
                for key, location in candidates[i].items():
                    picked.add(key)
                    pick_count += 1
                    counts[location[LK.locationType]] += 1
                    for nkey, distance in self.distance_cache[key].items():
                        if distance < Settings.sandbox_groups_distance_limit:
                            picked.add(nkey)  # don't need nearby
                apply_change(
                    group_change, candidates[i], capped=False, no_remove=self.no_remove
                )
                if pick_count >= Settings.sandbox_group_size:
                    # grabbed enough locations
                    break
                if all([counts[key] == self.limits[key] for key in counts]):
                    # all locations grabbed
                    break
            if len(group_change) > 0:
                suggestions.append(group_change)
        return suggestions

    def post_improvement(self, change):
        super().post_improvement(change)
        # Verification step if feeling unsure
        # verification = self.calculate_verification()
        # ver_total = verification[SK.gameScore][SK.total]
        # print(f"verification total {ver_total}")
        # if ver_total != round(total, 2):
        #     raise SystemExit(f"!!!!!! {round(total, 2)}")

        self.update_limits()
        for key in change:
            nearby = self.distance_cache[key]
            for nkey, distance in nearby.items():
                if distance < Settings.sandbox_too_near:
                    self.the_good.discard(nkey)

    def generate_additions(self, ignore):
        types = self.remaining_types_in_order()
        if len(types) == 0:
            return
        type = types[0]  # biggest type
        candidates = (
            (key, location)
            for key, location in self.possible_locations.items()
            if key not in ignore
        )
        f3 = 1
        f9 = 0
        if type == self.location_type[GK.groceryStoreLarge]:
            f3 = 1
            f9 = 1
        elif type == self.location_type[GK.groceryStore]:
            f3 = 0
            f9 = 1
        elif type == self.location_type[GK.kiosk]:
            f3 = 0
            f9 = 0
        for key, location in candidates:
            if key in self.solution:
                continue
            yield {
                key: bundle(
                    latitude=location[CK.latitude],
                    longitude=location[CK.longitude],
                    type=type,
                    f3=f3,
                    f9=f9,
                )
            }

    def generate_changes(self):
        locations = self.solution[LK.locations]
        for key, location in locations.items():
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
            if f9Count < Settings.max_stations:  # increase f9100
                yield {key: bundle(0, 1)}

    def generate_swaps(self):
        locations = self.solution[LK.locations]
        largeType = self.location_type[GK.groceryStoreLarge]
        for key, location in locations.items():
            if location[LK.locationType] == largeType:
                for k2, l2 in locations.items():
                    if l2[LK.locationType] != largeType:
                        yield {
                            key: bundle(
                                latitude=l2[CK.latitude], longitude=l2[CK.longitude]
                            ),
                            k2: bundle(
                                latitude=location[CK.latitude],
                                longitude=location[CK.longitude],
                            ),
                        }

    def update_limits(self):
        limits = {self.location_type[key]: val for key, val in KW.limits.items()}
        for location in self.solution[LK.locations].values():
            type = location[LK.locationType]
            limits[type] -= 1
        self.limits = limits

    def remaining_types_in_order(self):
        # order of salesVolume
        keys_in_order = [
            GK.groceryStoreLarge,
            GK.groceryStore,
            GK.gasStation,
            GK.convenience,
            GK.kiosk,
        ]
        types = []
        for key in keys_in_order:
            type = self.location_type[key]
            if self.limits[type] > 0:
                types.append(type)
        return types

    def tweak_locations(self, stale_progress=False):
        # generate a set of changes
        changes = []
        for change in self.generate_changes():
            changes.append(change)
        if stale_progress:
            map(changes.append, self.generate_swaps())
        # for change in self.generate_swaps():
        #     changes.append(change)
        #     for change in self.generate_moves(self.solution[LK.locations]):
        #         changes.append(change)
        #     for change in self.generate_consolidation(self.solution[LK.locations]):
        #         changes.append(change)

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
            totals.append(total)

        if (
            Settings.do_groups and len(improvements) > 2
        ):  # apply the group_size highest improvements that don't intersect
            group_change = {}
            picked = set()
            for i in sorted(
                improvements, key=lambda x: totals[x], reverse=True
            ):  # the indexes of the group_size highest totals
                if any([key in picked for key in changes[i]]):
                    continue
                for key in changes[i]:
                    picked.add(key)
                apply_change(
                    group_change, changes[i], capped=False, no_remove=self.no_remove
                )
                if len(picked) >= Settings.group_size:
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
            apply_change(
                self.solution[LK.locations], changes[index], no_remove=self.no_remove
            )
            print(f"tweak: {json.dumps(changes[index], indent=4)}")
            store(self.mapName, score)
        else:
            print(f"no tweak {total}")
