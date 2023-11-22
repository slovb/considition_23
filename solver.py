from abc import ABC, abstractmethod
import json
from typing import Callable, Dict, Generator, Iterable, List, Set

from data_keys import (
    CoordinateKeys as CK,
    LocationKeys as LK,
    GeneralKeys as GK,
)
from helper import apply_change, bundle
from scoring import distanceBetweenPoint
from settings import Settings
from store import store
from suggestion import ScoredSuggestion, Suggestion, STag


def abs_angle_change(la1: float, lo1: float, la2: float, lo2: float) -> float:
    return abs(la2 - la1) + abs(lo2 - lo1)


class Solver(ABC):
    def __init__(self, mapName: str, mapEntity: Dict, generalData: Dict) -> None:
        self.mapName = mapName
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.distance_cache: Dict[str, Dict] = {}
        self.location_type: Dict[str, str] = {}
        self.best = 0.0
        self.best_id: str = ""
        self.solution: Dict[str, Dict] = {"locations": {}}

        self.no_remove = False
        self.do_sets = Settings.do_sets
        self.the_good: Set[str] = set()
        self.the_bad: Set[str] = set()
        self.the_ugly: Set[str] = set()
        self.stale_progress = False
        super().__init__()

    @abstractmethod
    def list_actions(
        self,
    ) -> List[Callable[[List[ScoredSuggestion]], Iterable[Suggestion]]]:
        return []

    @abstractmethod
    def post_improvement(self, change: ScoredSuggestion) -> None:
        pass

    @abstractmethod
    def calculate(self, suggestion: Suggestion) -> ScoredSuggestion:
        pass

    @abstractmethod
    def initialize(self) -> None:
        self.location_type = {}
        for key in [
            GK.gasStation,
            GK.groceryStore,
            GK.groceryStoreLarge,
            GK.kiosk,
            GK.convenience,
        ]:
            self.location_type[key] = self.generalData[GK.locationTypes][key][GK.type_]

    def rebuild_distance_cache(self, locations: Dict[str, Dict]) -> None:
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

    def generate_moves(
        self, locations: Dict[str, Dict]
    ) -> Generator[Suggestion, None, None]:
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
                for key in self.distance_cache[main_key]
                if key in self.solution[LK.locations]
            ]
            for sub_key in nearby:
                sub_loc = self.solution[LK.locations][sub_key]
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
                    yield Suggestion(change=change, tag=STag.change)

    def generate_consolidation(self, locations) -> Generator[Suggestion, None, None]:
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
                for key in self.distance_cache[main_key]
                if key in self.solution[LK.locations]
            ]
            if len(nearby) < 2:
                continue
            for i, sub_1_key in enumerate(nearby[:-1]):
                sub_1_loc = self.solution[LK.locations][sub_1_key]
                for sub_2_key in nearby[i + 1 :]:
                    sub_2_loc = self.solution[LK.locations][sub_2_key]
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
                        yield Suggestion(change=change, tag=STag.change)

    def score_suggestions(
        self, suggestions: Iterable[Suggestion]
    ) -> List[ScoredSuggestion]:
        scored_suggestions = list(map(self.calculate, suggestions))
        for scored_suggestion in scored_suggestions:
            if scored_suggestion.total > self.best:
                for key in scored_suggestion.change:
                    self.the_good.add(key)
            else:
                for key in scored_suggestion.change:
                    self.the_bad.add(key)
        return scored_suggestions

    def solve(self) -> None:
        while True:
            if self.do_sets:
                # these will be ignored
                self.the_ugly = self.the_bad.difference(self.the_good)
                self.the_good = set()
            else:
                self.the_ugly = set()

            # find and score suggestions in action order
            scored_suggestions: List[ScoredSuggestion] = []
            for action in self.list_actions():
                scored_suggestions += self.score_suggestions(action(scored_suggestions))

            # safety check if too much ignoring has happened
            if len(scored_suggestions) == 0:
                if self.do_sets:
                    self.do_sets = False
                    continue
                else:
                    break

            # find the best suggestion (replace with max statement when code can be tested)
            best_candidate = max(scored_suggestions, key=lambda x: x.total)

            if best_candidate.total > self.best:
                self.best = best_candidate.total
                self.best_id = best_candidate.get_game_id()
                print(f"change: {json.dumps(best_candidate.change, indent=4)}")
                apply_change(
                    self.solution[LK.locations],
                    best_candidate.change,
                    no_remove=self.no_remove,
                )
                store(self.mapName, best_candidate.score)
                self.stale_progress = False
                self.post_improvement(best_candidate)
            elif self.do_sets:
                self.do_sets = False
            elif not self.stale_progress:
                self.stale_progress = True
            else:
                break
