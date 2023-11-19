from dataclasses import dataclass
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
        GK.convenience: 20,
        GK.gasStation: 8,
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
        # TODO may need to format floats in submit
        changes = []
        for change in self.generate_changes():
            changes.append(change)

        # score changes
        if Settings.do_multiprocessing:
            with Pool(4) as pool:
                scores = pool.map(self.calculate, changes)
        else:
            scores = list(map(self.calculate, changes))

        # process scores, extract ids that improved and total scores
        totals = []
        for score in scores:
            total = score[SK.gameScore][SK.total]
            # print(total)
            totals.append(total)

        # apply the best change
        total = max(totals)
        if total > self.best:
            self.best = total
            index = totals.index(total)
            score = scores[index]
            self.best_id = score[SK.gameId]
            apply_change(self.solution[LK.locations], changes[index])
            store(self.mapName, score)

    def generate_changes(self):
        # TODO actually consider current solution
        for key, location in self.location_candidates.items():
            yield {
                key: bundle(
                    latitude=location[CK.latitude],
                    longitude=location[CK.longitude],
                    type=self.location_type[GK.groceryStoreLarge][GK.type_],
                    f3=1,
                    f9=0,
                )
            }
