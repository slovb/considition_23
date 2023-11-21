from multiprocessing import Pool

from data_keys import (
    LocationKeys as LK,
    GeneralKeys as GK,
    ScoringKeys as SK,
)
from helper import apply_change, bundle
from scoring import calculateScore
from original_scoring import calculateScore as originalCalculateScore
from settings import Settings
from solver import Solver, get_game_id, get_total


class RegularSolver(Solver):
    def __init__(self, mapName, mapEntity, generalData):
        super().__init__(mapName=mapName, mapEntity=mapEntity, generalData=generalData)

    def calculate(self, change):
        return calculateScore(
            self.mapName,
            self.solution,
            change,
            self.mapEntity,
            self.generalData,
            self.distance_cache,
        )

    def calculate_verification(self):
        return originalCalculateScore(
            self.mapName, self.solution, self.mapEntity, self.generalData
        )

    def initialize(self):
        super().initialize()
        if Settings.starting_point == "func":
            self.solution = self.starting_point()
        self.rebuild_cache()
        if Settings.starting_point == "func":
            score = self.calculate(self.solution)
            self.best = get_total(score)
            self.best_id = get_game_id(score)

    def starting_point(self):
        from helper import bundle

        solution = {LK.locations: {}}

        for key in self.mapEntity[LK.locations]:
            location = self.mapEntity[LK.locations][key]
            name = location[LK.locationName]
            type = location[LK.locationType]
            f3 = 1
            f9 = 0
            if type == self.location_type[GK.groceryStoreLarge]:
                f3 = 1
                f9 = 1
            solution[LK.locations][name] = bundle(f3=f3, f9=f9)
        return solution

    def rebuild_cache(self):
        locations = self.mapEntity[LK.locations]
        self.rebuild_distance_cache(locations)

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

    def find_candidates(self):
        changes = []
        for change in self.generate_changes(ignore=self.the_ugly):
            changes.append(change)
        if self.stale_progress:
            for change in self.generate_moves(self.mapEntity[LK.locations]):
                changes.append(change)
            for change in self.generate_consolidation(self.mapEntity[LK.locations]):
                changes.append(change)
        return changes

    def improve_scored_candidates(self, candidates, totals, scores):
        # process totals, extract ids that improved
        improvements = []
        for i, total in enumerate(totals):
            if total > self.best:  # improved total
                improvements.append(i)
                if self.do_sets:
                    for key in candidates[i]:
                        self.the_good.add(key)
            elif self.do_sets:  # not improved total
                for key in candidates[i]:
                    self.the_bad.add(key)

        # apply the group_size highest improvements that don't interact
        if Settings.do_groups and len(improvements) > 2:
            group_change = {}
            picked = set()
            pick_count = 0
            for i in sorted(
                improvements, key=lambda x: totals[x], reverse=True
            ):  # the indexes of the group_size highest totals
                if any([key in picked for key in candidates[i]]):
                    continue
                for key in candidates[i]:
                    picked.add(key)
                    pick_count += 1
                    for nkey, distance in self.distance_cache[key].items():
                        if distance < Settings.groups_distance_limit:
                            picked.add(nkey)  # don't need nearby
                apply_change(group_change, candidates[i], capped=False)
                if pick_count >= Settings.group_size:
                    break
            candidates.append(group_change)
            group_score = self.calculate(group_change)
            scores.append(group_score)
            totals.append(get_total(group_score))
