from typing import Callable, Dict, Generator, Iterable, List
from data_keys import (
    LocationKeys as LK,
    GeneralKeys as GK,
)
from helper import build_distance_cache, bundle
from scoring import calculateScore
from original_scoring import calculateScore as originalCalculateScore
from settings import Settings
from solver import Solver
from suggestion import ScoredSuggestion, Suggestion, STag


class RegularSolver(Solver):
    def __init__(self, mapName: str, mapEntity: Dict, generalData: Dict) -> None:
        super().__init__(mapName=mapName, mapEntity=mapEntity, generalData=generalData)

    def list_actions(
        self,
    ) -> List[Callable[[List[ScoredSuggestion]], Iterable[Suggestion]]]:
        return [self.find_suggestions, self.group_scored_suggestions]

    def calculate(self, suggestion: Suggestion) -> ScoredSuggestion:
        return ScoredSuggestion(
            suggestion=suggestion,
            score=calculateScore(
                self.mapName,
                self.solution,
                suggestion.change,
                self.mapEntity,
                self.generalData,
                self.distance_cache,
            ),
        )

    def calculate_verification(self) -> Dict[str, Dict]:
        return originalCalculateScore(
            self.mapName, self.solution, self.mapEntity, self.generalData
        )

    def initialize(self) -> None:
        super().initialize()
        if Settings.starting_point == "func":
            self.solution = self.starting_point()
        self.rebuild_cache()
        if Settings.starting_point == "func":
            suggestion = Suggestion(change={}, tag=STag.start)
            scored_suggestion = self.calculate(suggestion)
            self.best = scored_suggestion.total
            self.best_id = scored_suggestion.get_game_id()

    def starting_point(self) -> Dict[str, Dict]:
        from helper import bundle

        solution: Dict[str, Dict] = {LK.locations: {}}

        for key in self.mapEntity[LK.locations]:
            location = self.mapEntity[LK.locations][key]
            name = location[LK.locationName]
            type = location[LK.locationType]
            f3 = 1
            f9 = 0
            # if type == self.location_type[GK.groceryStoreLarge]:
            #     f3 = 0
            #     f9 = 2
            # elif type == self.location_type[GK.groceryStore]:
            #     f3 = 0
            #     f9 = 1
            # elif type == self.location_type[GK.gasStation]:
            #     f3 = 2
            #     f9 = 0
            solution[LK.locations][name] = bundle(f3=f3, f9=f9)
        return solution

    def rebuild_cache(self) -> None:
        locations = self.mapEntity[LK.locations]
        self.distance_cache = build_distance_cache(locations, self.generalData)

    def generate_changes(
        self, locations: Dict[str, Dict]
    ) -> Generator[Suggestion, None, None]:
        for key in (key for key in locations if key not in self.the_ugly):
            location = locations[key]
            f3Count = location[LK.f3100Count]
            f9Count = location[LK.f9100Count]
            if f3Count > 0:  # decrease f3100
                yield Suggestion(change={key: bundle(-1, 0)}, tag=STag.change)
            if f3Count > 0 and f9Count < Settings.max_stations:  # f3100 -> f9100
                yield Suggestion(change={key: bundle(-1, 1)}, tag=STag.change)
            if f3Count > 1 and f9Count < Settings.max_stations:  # 2 f3100 -> f9100
                yield Suggestion(change={key: bundle(-2, 1)}, tag=STag.change)
            if f9Count > 0 and f3Count < Settings.max_stations:  # f9100 -> f3100
                yield Suggestion(change={key: bundle(1, -1)}, tag=STag.change)
            if f9Count > 0 and f3Count == 0:  # f9100 -> 2 f3100
                yield Suggestion(change={key: bundle(2, -1)}, tag=STag.change)
            if f3Count < Settings.max_stations:  # increase f3100
                yield Suggestion(change={key: bundle(1, 0)}, tag=STag.change)
        for key in (
            key for key in self.mapEntity[LK.locations] if key not in self.the_ugly
        ):  # try to add a missing location
            if key not in locations:
                yield Suggestion(change={key: bundle(1, 0)}, tag=STag.change)
                yield Suggestion(change={key: bundle(2, 0)}, tag=STag.change)
                yield Suggestion(change={key: bundle(0, 1)}, tag=STag.change)

    def find_suggestions(self, _: List[ScoredSuggestion]) -> List[Suggestion]:
        suggestions = []
        for change in self.generate_changes(self.solution[LK.locations]):
            suggestions.append(change)
        if self.stale_progress:
            for change in self.generate_moves(self.mapEntity[LK.locations]):
                suggestions.append(change)
            for change in self.generate_consolidation(self.mapEntity[LK.locations]):
                suggestions.append(change)
        return suggestions

    def post_improvement(self, change):
        return super().post_improvement(change)
