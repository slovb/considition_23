from dataclasses import dataclass
import json
from multiprocessing import Pool

from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    HotspotKeys as HK,
    LocationKeys as LK,
    MapKeys as MK,
    ScoringKeys as SK,
)
from helper import apply_change, bundle
from scoring import distanceBetweenPoint, calculateScore
from settings import Settings
from store import store


@dataclass
class KW:
    limit = "limit"
    limits = {
        GK.groceryStoreLarge: 5,
        GK.groceryStore: 20,
        GK.gasStation: 8,
        GK.convenience: 20,
        GK.kiosk: 3,
    }
    nearby = "nearby"


class SandboxSolver:
    def __init__(self, mapName, mapEntity, generalData):
        self.mapName = mapName
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.hotspot_cache = {}
        self.location_candidates = {}
        self.distance_cache = {}
        self.location_type = {}
        self.best = 0
        self.best_id = None
        self.solution = {"locations": {}}

    def calculate(self, change):
        names = {}
        reverted = {}

        def generate_names(solution, change):
            i = 1
            for key in solution[LK.locations]:
                yield key, f"location{i}"
                i += 1
            for key in change:
                if key not in solution[LK.locations]:
                    yield key, f"location{i}"
                    i += 1

        for key, name in generate_names(self.solution, change):
            names[key] = name
            reverted[name] = key
        return calculateScore(
            self.mapName,
            self.solution,
            change,
            self.mapEntity,
            self.generalData,
            self.distance_cache,
            names,
            reverted,
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
            self.location_type[key] = {
                GK.type_: self.generalData[GK.locationTypes][key][GK.type_],
                GK.salesVol: self.generalData[GK.locationTypes][key][GK.salesVol],
                KW.limit: KW.limits[key],
            }
        self.latitudeMax = self.mapEntity[MK.border][MK.latitudeMax]
        self.latitudeMin = self.mapEntity[MK.border][MK.latitudeMin]
        self.longitudeMax = self.mapEntity[MK.border][MK.longitudeMax]
        self.longitudeMin = self.mapEntity[MK.border][MK.longitudeMin]
        self.lla = lambda la: min(self.latitudeMax, max(self.latitudeMin, la))
        self.llo = lambda lo: min(self.longitudeMax, max(self.longitudeMin, lo))
        self.update_limits()

    def rebuild_cache(self):
        self.rebuild_hotspot_cache()
        self.rebuild_location_candidates()
        self.rebuild_distance_cache()

    def rebuild_hotspot_cache(self):
        hotspots = self.mapEntity[HK.hotspots]
        hotspot_cache = {}
        keys = []
        for key, hotspot in enumerate(hotspots):
            keys.append(key)
            hotspot_cache[key] = hotspot
            hotspot_cache[key][KW.nearby] = {}
        for i, i_key in enumerate(keys[:-1]):
            i_lat = hotspot_cache[i_key][CK.latitude]
            i_long = hotspot_cache[i_key][CK.longitude]
            for j_key in keys[i + 1 :]:
                j_lat = hotspot_cache[j_key][CK.latitude]
                j_long = hotspot_cache[j_key][CK.longitude]
                distance = distanceBetweenPoint(i_lat, i_long, j_lat, j_long)
                if distance < self.generalData[GK.willingnessToTravelInMeters]:
                    hotspot_cache[i_key][KW.nearby][j_key] = distance
                    hotspot_cache[j_key][KW.nearby][i_key] = distance
        self.hotspot_cache = hotspot_cache

    def rebuild_location_candidates(self):
        candidates = {}
        i = 1
        taken = set()

        def adder(i, latitude, longitude):
            la = self.lla(latitude)
            lo = self.llo(longitude)
            if (la, lo) not in taken:
                candidates[f"candidate{i}"] = bundle(
                    latitude=la,
                    longitude=lo,
                )
                taken.add((la, lo))
                return i + 1
            return i

        for hotspot in self.hotspot_cache.values():
            hotspot_la = hotspot[CK.latitude]
            hotspot_lo = hotspot[CK.longitude]
            hotspot_w = hotspot[HK.spread] * hotspot[LK.footfall]
            # add the hotspot as a location
            i = adder(i, hotspot_la, hotspot_lo)

            # start collecting a cluster node
            cluster_la = hotspot_la * hotspot_w
            cluster_lo = hotspot_lo * hotspot_w
            cluster_w = hotspot_w

            for neighbor_key in hotspot[KW.nearby]:
                neighbor = self.hotspot_cache[neighbor_key]
                neighbor_la = neighbor[CK.latitude]
                neighbor_lo = neighbor[CK.longitude]
                neighbor_w = neighbor[HK.spread] * neighbor[LK.footfall]

                # add the weighted average of the two points
                avg_la = (hotspot_la * hotspot_w + neighbor_la * neighbor_w) / (
                    hotspot_w + neighbor_w
                )
                avg_lo = (hotspot_lo * hotspot_w + neighbor_lo * neighbor_w) / (
                    hotspot_w + neighbor_w
                )
                i = adder(i, avg_la, avg_lo)

                # increase the clusterpoint
                cluster_la += neighbor_la * neighbor_w
                cluster_lo += neighbor_lo * neighbor_w
                cluster_w += neighbor_w

            # add the clusterpoint
            cluster_la = cluster_la / cluster_w
            cluster_lo = cluster_lo / cluster_w
            i = adder(i, cluster_la, cluster_lo)

        print(f"{len(candidates)} candidates, remove near nodes later")
        self.location_candidates = candidates

    def rebuild_distance_cache(self):
        locations = self.location_candidates
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

    def solve(self):
        the_good = set()
        the_bad = set()
        the_ugly = set()
        do_sets = Settings.do_sandbox_sets

        old_best = self.best
        stale_progress = False
        while True:
            if do_sets:
                the_ugly = the_bad.difference(the_good)  # these will be ignored
                the_good = set()
            else:
                the_ugly = set()

            #
            self.add_location(the_good=the_good, the_bad=the_bad, ignore=the_ugly)
            self.tweak_locations(stale_progress=stale_progress)
            if self.best > old_best:
                old_best = self.best
                stale_progress = False
            elif do_sets:
                do_sets = False
            elif not stale_progress:
                stale_progress = True
            else:
                break

    def add_location(self, the_good, the_bad, ignore):
        print(f"len ignore {len(ignore)}")
        remaining_types = self.remaining_types_in_order()
        if len(remaining_types) == 0:
            return

        # try to add locations
        changes = []
        for change in self.generate_additions(ignore=ignore):
            changes.append(change)

        # score additions
        if Settings.do_multiprocessing:
            with Pool(4) as pool:
                scores = pool.map(self.calculate, changes)
        else:
            scores = list(map(self.calculate, changes))

        # process scores, extract ids that improved and total scores
        totals = []
        for i, score in enumerate(scores):
            total = score[SK.gameScore][SK.total]
            if total > self.best:
                for key in changes[i]:
                    the_good.add(key)
            else:
                for key in changes[i]:
                    the_bad.add(key)
            totals.append(total)
        print(len(the_good), len(the_bad))

        # try adjustments of the best additions
        suggestions = []
        adjust_how_many = Settings.sandbox_explore_how_many
        for i in sorted(range(len(changes)), key=lambda x: totals[x], reverse=True):
            change = changes[i]
            for type in remaining_types:
                for f_count in [(1, 0), (0, 1), (0, Settings.max_stations)]:
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

        # merge and process suggestions into the state
        for suggestion in suggestions:
            changes.append(suggestion)
            score = self.calculate(suggestion)
            scores.append(score)
            totals.append(score[SK.gameScore][SK.total])

        if (
            Settings.do_sandbox_groups
        ):  # apply the group_size highest improvements that don't intersect or are nearby
            group_change = {}
            picked = set()
            pick_count = 0
            counts = {key: 0 for key in self.limits}
            for i in sorted(range(len(changes)), key=lambda x: totals[x], reverse=True):
                # looping through the indexes of the highest totals
                if any([key in picked for key in changes[i]]):
                    continue
                too_much = False
                for type, count in counts.items():
                    add = len(
                        [
                            key
                            for key, location in change.items()
                            if location[LK.locationType] == type
                        ]
                    )
                    if add + count >= self.limits[type]:
                        too_much = True
                        break
                if too_much:
                    continue
                for key, location in changes[i].items():
                    picked.add(key)
                    pick_count += 1
                    counts[location[LK.locationType]] += 1
                    for nkey, distance in self.distance_cache[key].items():
                        if distance < Settings.sandbox_groups_distance_limit:
                            picked.add(nkey)  # don't need nearby
                apply_change(group_change, changes[i], capped=False)
                if pick_count >= Settings.sandbox_group_size:
                    # grabbed enough locations
                    break
                if all([counts[key] == self.limits[key] for key in counts]):
                    # all locations grabbed
                    break
            if len(group_change) > 0:
                changes.append(group_change)
                group_score = self.calculate(group_change)
                # print("?" * 80)
                # print(json.dumps(group_change, indent=4))
                # print(json.dumps(group_score[SK.gameScore][SK.total], indent=4))
                # print("=" * 80)
                scores.append(group_score)
                totals.append(group_score[SK.gameScore][SK.total])

        if len(totals) == 0:  # safety check due to ignore
            return

        # apply the best change
        total = max(totals)
        if total > self.best:
            self.best = total
            index = totals.index(total)
            score = scores[index]
            self.best_id = score[SK.gameId]
            apply_change(self.solution[LK.locations], changes[index])
            print(f"addition: {json.dumps(changes[index], indent=4)}")
            store(self.mapName, score)
            self.update_limits()
            for key in changes[index]:
                nearby = self.distance_cache[key]
                for nkey, distance in nearby.items():
                    if distance < Settings.sandbox_too_near:
                        the_good.discard(nkey)
        else:
            print(f"no additions {total}")

    def tweak_locations(self, stale_progress=False):
        # generate a set of changes
        changes = []
        for change in self.generate_changes():
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
                apply_change(group_change, changes[i], capped=False)
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
            apply_change(self.solution[LK.locations], changes[index])
            print(f"tweak: {json.dumps(changes[index], indent=4)}")
            store(self.mapName, score)
        else:
            print(f"no tweak {total}")

    def generate_additions(self, ignore):
        types = self.remaining_types_in_order()
        if len(types) == 0:
            return
        type = types[0]  # biggest type
        candidates = (
            (key, location)
            for key, location in self.location_candidates.items()
            if key not in ignore
        )
        for key, location in candidates:
            if key in self.solution:
                continue
            yield {
                key: bundle(
                    latitude=location[CK.latitude],
                    longitude=location[CK.longitude],
                    type=type,
                    f3=0,
                    f9=1,
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

    def generate_moves(self):
        locations = self.solution[LK.locations]
        # locations = self.location_candidates # won't work as this code can't create types or add coords
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
        locations = self.solution[LK.locations]
        # locations = self.location_candidates  # won't work as this code can't create types or add coords
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

    def update_limits(self):
        limits = {
            self.location_type[key][GK.type_]: val for key, val in KW.limits.items()
        }
        for location in self.solution[LK.locations].values():
            type = location[LK.locationType]
            limits[type] -= 1
        self.limits = limits

    def remaining_types_in_order(self):  # order of salesVolume
        keys_in_order = [
            GK.groceryStoreLarge,
            GK.groceryStore,
            GK.gasStation,
            GK.convenience,
            GK.kiosk,
        ]
        types = []
        for key in keys_in_order:
            type = self.location_type[key][GK.type_]
            if self.limits[type] > 0:
                types.append(type)
        return types
