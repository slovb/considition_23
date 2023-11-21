from abc import ABC, abstractmethod
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


def abs_angle_change(la1, lo1, la2, lo2):
    return abs(la2 - la1) + abs(lo2 - lo1)


def get_total(score):
    return score[SK.gameScore][SK.total]


def get_game_id(score):
    return score[SK.gameId]


class Solver(ABC):
    def __init__(self, mapName, mapEntity, generalData):
        self.mapName = mapName
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.distance_cache = {}
        self.location_type = {}
        self.best = 0
        self.best_id = None
        self.solution = {"locations": {}}

        self.do_sets = Settings.do_sets
        self.the_good = set()
        self.the_bad = set()
        self.the_ugly = set()
        self.stale_progress = False
        super().__init__()

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
        self.location_type = {}
        for key in [
            GK.gasStation,
            GK.groceryStore,
            GK.groceryStoreLarge,
            GK.kiosk,
            GK.convenience,
        ]:
            self.location_type[key] = self.generalData[GK.locationTypes][key][GK.type_]

    def rebuild_distance_cache(self, locations):
        keys = []
        lats = []
        longs = []
        willingnessToTravelInMeters = self.generalData[GK.willingnessToTravelInMeters]
        way_too_far = 1.0
        for key, location in locations.items():
            keys.append(key)
            self.distance_cache[key] = {}
            lats.append(location[CK.latitude])
            longs.append(location[CK.longitude])
        for i in range(len(lats) - 1):
            for j in range(i + 1, len(lats)):
                abc = abs_angle_change(lats[i], longs[i], lats[j], longs[j])
                if abc > way_too_far:  # very rough distance limit
                    continue
                distance = distanceBetweenPoint(lats[i], longs[i], lats[j], longs[j])
                if distance < willingnessToTravelInMeters:
                    self.distance_cache[keys[i]][keys[j]] = distance
                    self.distance_cache[keys[j]][keys[i]] = distance
                else:
                    way_too_far = min(way_too_far, 10.0 * abc)

    def generate_moves(self, locations):
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

    def generate_consolidation(self, locations):
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

    @abstractmethod
    def find_candidates(self):
        pass

    @abstractmethod
    def improve_scored_candidates(self, candidates, totals, scores):
        pass

    def solve(self):
        while True:
            if self.do_sets:
                # these will be ignored
                self.the_ugly = self.the_bad.difference(self.the_good)
                self.the_good = set()
            else:
                self.the_ugly = set()

            candidates = self.find_candidates()

            # score candidates
            if Settings.do_multiprocessing:
                with Pool(4) as pool:
                    scores = pool.map(self.calculate, candidates)
            else:
                scores = list(map(self.calculate, candidates))

            # process scores, extract total scores
            totals = []
            for score in scores:
                total = get_total(score)
                totals.append(total)

            # safety check if too much ignoring has happened
            if len(totals) == 0:
                if self.do_sets:
                    self.do_sets = False
                    continue
                else:
                    break

            self.improve_scored_candidates(
                candidates=candidates, totals=totals, scores=scores
            )

            # apply the best change
            total = max(totals)
            if total > self.best:
                self.best = total
                index = totals.index(total)
                score = scores[index]
                self.best_id = get_game_id(score)
                apply_change(self.solution[LK.locations], candidates[index])
                store(self.mapName, score)
                self.stale_progress = False
            elif self.do_sets:
                self.do_sets = False
            elif not self.stale_progress:
                self.stale_progress = True
            else:
                break
