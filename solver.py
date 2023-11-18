from data_keys import (
    CoordinateKeys as CK,
    LocationKeys as LK,
    GeneralKeys as GK,
    GeneralKeys as GK,
    CoordinateKeys as CK,
)
from helper import bundle
from scoring import distanceBetweenPoint, calculateScore
from settings import Settings


class Solver():
    def __init__(self, mapName, solution, mapEntity, generalData):
        self.mapName = mapName
        self.solution = solution
        self.mapEntity = mapEntity
        self.generalData = generalData
        self.distance_cache = {}

    def calculate(self, change):
        return calculateScore(self.mapName, self.solution, change, self.mapEntity, self.generalData, self.distance_cache)
    
    def rebuild_distance_cache(self):
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

    def generate_changes(self, ignore = set()):
        locations = self.solution[LK.locations]
        for key in (key for key in locations if key not in ignore):
            location = locations[key]
            f3Count = location[LK.f3100Count]
            f9Count = location[LK.f9100Count]
            if f3Count > 0: # decrease f3100
                yield { key: bundle(-1, 0) }
            if f3Count > 0 and f9Count < Settings.max_stations: # f3100 -> f9100
                yield { key: bundle(-1, 1) }
            if f3Count > 1 and f9Count < Settings.max_stations: # 2 f3100 -> f9100
                yield { key: bundle(-2, 1) }
            if f9Count > 0 and f3Count < Settings.max_stations: # f9100 -> f3100
                yield { key: bundle(1, -1) }
            if f3Count < Settings.max_stations: # increase f3100
                yield { key: bundle(1, 0) }
        for key in (key for key in self.mapEntity[LK.locations] if key not in ignore): # try to add a missing location
            if key not in locations:
                yield { key: bundle(1, 0) }

    def generate_moves(self):
        locations = self.mapEntity[LK.locations]
        for main_key in locations:
            main_location = self.solution[LK.locations].get(main_key)
            if main_location is not None and main_location[LK.f3100Count] == Settings.max_stations and main_location[LK.f9100Count] == Settings.max_stations:
                continue
            nearby = [key for key in self.distance_cache.get(main_key) if key in self.solution[LK.locations]]
            for sub_key in nearby:
                sub_loc = self.solution[LK.locations].get(sub_key)
                changes = []
                if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
                    changes.append({ main_key: bundle(1, 0) })
                if main_location is None or main_location[LK.f9100Count] < Settings.max_stations:
                    changes.append({ main_key: bundle(0, 1) })
                if main_location is not None and main_location[LK.f3100Count] > 0 and main_location[LK.f9100Count] < Settings.max_stations:
                    changes.append({ main_key: bundle(-1, 1) })
                for change in changes:
                    if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
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
            if main_location is not None and main_location[LK.f3100Count] == Settings.max_stations and main_location[LK.f9100Count] == Settings.max_stations:
                continue
            nearby = [key for key in self.distance_cache.get(main_key) if key in self.solution[LK.locations]]
            if len(nearby) < 2:
                continue
            for i, sub_1_key in enumerate(nearby[:-1]):
                sub_1_loc = self.solution[LK.locations].get(sub_1_key)
                for sub_2_key in nearby[i+1:]:
                    sub_2_loc = self.solution[LK.locations].get(sub_2_key)
                    changes = []
                    if main_location is None or main_location[LK.f3100Count] < Settings.max_stations:
                        changes.append({ main_key: bundle(1, 0) })
                    if main_location is None or main_location[LK.f9100Count] < Settings.max_stations:
                        changes.append({ main_key: bundle(0, 1) })
                    if main_location is not None and main_location[LK.f3100Count] > 0 and main_location[LK.f9100Count] < Settings.max_stations:
                        changes.append({ main_key: bundle(-1, 1) })
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
