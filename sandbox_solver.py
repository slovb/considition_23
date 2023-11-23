from typing import Callable, Dict, Generator, Iterable, List
from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    LocationKeys as LK,
    MapKeys as MK,
)
from helper import apply_change, build_distance_cache, bundle
from map_limiter import MapLimiter
from sandbox_helper import build_hotspot_cache, find_possible_locations, temporary_names
from scoring import calculateScore
from original_scoring import calculateScore as originalCalculateScore
from settings import Settings, KW
from solver import Solver
from suggestion import ScoredSuggestion, Suggestion, STag


class SandboxSolver(Solver):
    def __init__(self, mapName: str, mapEntity: Dict, generalData: Dict) -> None:
        super().__init__(mapName=mapName, mapEntity=mapEntity, generalData=generalData)

        self.hotspot_cache: Dict = {}
        self.hotspot_footfall_cache: Dict = {}
        self.possible_locations: Dict[str, Dict] = {}
        self.no_remove = False

    def calculate(
        self, suggestion: Suggestion, skip_validation=True
    ) -> ScoredSuggestion:
        names, inverse = temporary_names(self.solution, suggestion.change)
        return ScoredSuggestion(
            suggestion=suggestion,
            score=calculateScore(
                mapName=self.mapName,
                solution=self.solution,
                change=suggestion.change,
                mapEntity=self.mapEntity,
                generalData=self.generalData,
                distance_cache=self.distance_cache,
                sandbox_names=names,
                inverse_sandbox_names=inverse,
                skip_validation=skip_validation,
                hotspot_footfall_cache=self.hotspot_footfall_cache,
            ),
        )

    def list_actions(
        self,
    ) -> List[Callable[[List[ScoredSuggestion]], Iterable[Suggestion]]]:
        return [
            self.find_new_locations,
            self.wary_the_best,
            self.sandbox_groups,
            self.tweak_state,
        ]

    def calculate_verification(self) -> Dict[str, Dict]:
        solution: Dict[str, Dict] = {LK.locations: {}}
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

    def initialize(self) -> None:
        super().initialize()
        self.map_limiter = MapLimiter(
            latitudeMin=self.mapEntity[MK.border][MK.latitudeMin],
            latitudeMax=self.mapEntity[MK.border][MK.latitudeMax],
            longitudeMin=self.mapEntity[MK.border][MK.longitudeMin],
            longitudeMax=self.mapEntity[MK.border][MK.longitudeMax],
        )
        self.update_limits()
        self.rebuild_cache()

    def rebuild_cache(self) -> None:
        self.hotspot_cache = build_hotspot_cache(
            mapEntity=self.mapEntity, generalData=self.generalData
        )
        self.possible_locations = find_possible_locations(
            hotspot_cache=self.hotspot_cache, map_limiter=self.map_limiter
        )
        self.distance_cache = build_distance_cache(
            self.possible_locations, self.generalData
        )

    def find_new_locations(self, _: List[ScoredSuggestion]) -> Iterable[Suggestion]:
        remaining_types = self.remaining_types_in_order()
        if len(remaining_types) == 0:
            return []
        elif len(remaining_types) == 1:
            # get those last kiosks
            self.no_remove = True
        print(self.limits)

        # try to add locations
        return self.generate_additions()

    def wary_the_best(
        self, scored_suggestions: List[ScoredSuggestion]
    ) -> List[Suggestion]:
        suggestions = []

        remaining_types = self.remaining_types_in_order()
        # try adjustments of the best additions
        adjust_how_many = Settings.sandbox_explore_how_many
        if adjust_how_many > 0:
            for scored_suggestion in sorted(
                scored_suggestions, key=lambda x: x.total, reverse=True
            ):
                if scored_suggestion.tag != STag.add:
                    continue
                for type in remaining_types:
                    for f_count in [(1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]:
                        change = {}
                        for loc_key, location in scored_suggestion.change.items():
                            if (
                                type == location[LK.locationType]
                                and f_count[0] == location[LK.f3100Count]
                                and f_count[1] == location[LK.f9100Count]
                            ):  # no repeats
                                continue
                            change[loc_key] = bundle(
                                latitude=location[CK.latitude],
                                longitude=location[CK.longitude],
                                type=type,
                                f3=f_count[0],
                                f9=f_count[1],
                            )
                        suggestions.append(Suggestion(change=change, tag=STag.change))
                adjust_how_many -= 1
                if adjust_how_many <= 0:
                    break
        return suggestions

    def tweak_state(
        self, _: List[ScoredSuggestion]
    ) -> Generator[Suggestion, None, None]:
        # tweaks to be separated later
        for suggestion in self.generate_changes():
            yield suggestion
        if self.stale_progress:
            for suggestion in self.generate_swaps(self.solution[LK.locations]):
                yield suggestion
            for suggestion in self.generate_moves(self.solution[LK.locations]):
                yield suggestion
            for suggestion in self.generate_consolidation(self.solution[LK.locations]):
                yield suggestion

    def sandbox_groups(
        self, scored_suggestions: List[ScoredSuggestion]
    ) -> List[Suggestion]:
        suggestions = []

        if (
            Settings.do_sandbox_groups
        ):  # apply the group_size highest improvements that don't intersect or are nearby
            group_change: Dict[str, Dict] = {}
            picked = set()
            pick_count = 0
            counts = {key: 0 for key in self.limits}
            for scored_suggestion in sorted(
                scored_suggestions, key=lambda x: x.total, reverse=True
            ):
                if scored_suggestion.tag != STag.add:
                    continue
                # looping through the indexes of the highest totals
                if any([key in picked for key in scored_suggestion.change]):
                    continue
                too_much = False
                for type, count in counts.items():
                    add = len(
                        [
                            key
                            for key, location in scored_suggestion.change.items()
                            if location[LK.locationType] == type
                        ]
                    )
                    if add + count >= self.limits[type]:
                        too_much = True
                        break
                if too_much:
                    continue
                for key, location in scored_suggestion.change.items():
                    picked.add(key)
                    pick_count += 1
                    counts[location[LK.locationType]] += 1
                    for nkey, distance in self.distance_cache[key].items():
                        if distance < Settings.sandbox_groups_distance_limit:
                            picked.add(nkey)  # don't need nearby
                apply_change(
                    group_change,
                    scored_suggestion.change,
                    capped=False,
                    no_remove=self.no_remove,
                )
                if pick_count >= Settings.sandbox_group_size:
                    # grabbed enough locations
                    break
                if all([counts[key] == self.limits[key] for key in counts]):
                    # all locations grabbed
                    break
            if len(group_change) > 0:
                suggestions.append(Suggestion(change=group_change, tag=STag.group))
        return suggestions

    def post_improvement(self, suggestion: ScoredSuggestion):
        super().post_improvement(suggestion)
        # Verification step if feeling unsure
        # verification = self.calculate_verification()
        # ver_total = verification[SK.gameScore][SK.total]
        # print(f"verification total {ver_total}")
        # if ver_total != round(total, 2):
        #     raise SystemExit(f"!!!!!! {round(total, 2)}")

        self.update_limits()
        for key in suggestion.change:
            nearby = self.distance_cache[key]
            for nkey, distance in nearby.items():
                if distance < Settings.sandbox_too_near:
                    self.the_good.discard(nkey)

    def generate_additions(self) -> Generator[Suggestion, None, None]:
        types = self.remaining_types_in_order()
        if len(types) == 0:
            return
        type = types[0]  # biggest type
        candidates = (
            (key, location)
            for key, location in self.possible_locations.items()
            if key not in self.the_ugly
        )
        f3 = 1
        f9 = 0
        if type == self.location_type[GK.groceryStoreLarge]:
            f3 = 2
            f9 = 0
        elif type == self.location_type[GK.groceryStore]:
            f3 = 2
            f9 = 0
        elif type == self.location_type[GK.kiosk]:
            f3 = 0
            f9 = 0
        for key, location in candidates:
            if key in self.solution:
                continue
            yield Suggestion(
                change={
                    key: bundle(
                        latitude=location[CK.latitude],
                        longitude=location[CK.longitude],
                        type=type,
                        f3=f3,
                        f9=f9,
                    )
                },
                tag=STag.add,
            )

    def generate_changes(self) -> Generator[Suggestion, None, None]:
        locations = self.solution[LK.locations]
        for key, location in locations.items():
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
            if f3Count < Settings.max_stations:  # increase f3100
                yield Suggestion(change={key: bundle(1, 0)}, tag=STag.change)
            if f9Count < Settings.max_stations:  # increase f9100
                yield Suggestion(change={key: bundle(0, 1)}, tag=STag.change)

    def generate_swaps(
        self, locations: Dict[str, Dict]
    ) -> Generator[Suggestion, None, None]:
        largeType = self.location_type[GK.groceryStoreLarge]
        for key, location in locations.items():
            if location[LK.locationType] == largeType:
                for k2, l2 in locations.items():
                    if l2[LK.locationType] != largeType:
                        yield Suggestion(
                            change={
                                key: bundle(
                                    latitude=l2[CK.latitude], longitude=l2[CK.longitude]
                                ),
                                k2: bundle(
                                    latitude=location[CK.latitude],
                                    longitude=location[CK.longitude],
                                ),
                            },
                            tag=STag.change,
                        )

    def update_limits(self) -> None:
        limits = {self.location_type[key]: val for key, val in KW.limits.items()}
        for location in self.solution[LK.locations].values():
            type = location[LK.locationType]
            limits[type] -= 1
        self.limits = limits

    def remaining_types_in_order(self) -> List[str]:
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
