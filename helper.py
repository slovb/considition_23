import math
from typing import Any, Dict, Optional

import numpy as np
from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    LocationKeys as LK,
)

from settings import Settings


def abs_angle_change(la1: float, lo1: float, la2: float, lo2: float) -> float:
    return abs(la2 - la1) + abs(lo2 - lo1)


def distanceBetweenPoint(lat_1, long_1, lat_2, long_2) -> float:
    R = 6371e3
    φ1 = lat_1 * math.pi / 180  #  φ, λ in radians
    φ2 = lat_2 * math.pi / 180
    Δφ = (lat_2 - lat_1) * math.pi / 180
    Δλ = (long_2 - long_1) * math.pi / 180

    a = np.sin(Δφ / 2) * np.sin(Δφ / 2) + np.cos(φ1) * np.cos(φ2) * np.sin(
        Δλ / 2
    ) * np.sin(Δλ / 2)

    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    d = R * c

    return round(d, 0)


def apply_change(
    locations: Dict[str, Dict],
    change: Dict[str, Dict],
    capped: bool = True,
    no_remove: bool = False,
) -> None:
    for key, mod in change.items():
        if key not in locations:
            locations[key] = mod
        else:
            for mkey, mval in mod.items():
                if mkey in [LK.f3100Count, LK.f9100Count]:
                    locations[key][mkey] = locations[key][mkey] + mval
                else:
                    locations[key][mkey] = mval
            # if (
            #     locations[key][LK.f3100Count] == 0
            #     and locations[key][LK.f9100Count] == 0
            # ):
            #     del locations[key]
    if capped:
        to_remove = []
        for loc_key, loc in locations.items():
            for key, val in loc.items():
                if key in [LK.f3100Count, LK.f9100Count]:
                    if val < 0 or val > Settings.max_stations:
                        loc[key] = min(Settings.max_stations, max(0, val))
            if loc[LK.f3100Count] == 0 and loc[LK.f9100Count] == 0:
                to_remove.append(loc_key)
        if not no_remove:
            for key in to_remove:
                del locations[key]


def bundle(
    f3: Optional[int] = None,
    f9: Optional[int] = None,
    type: Optional[str] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if f3 is not None:
        out[LK.f3100Count] = f3
    if f9 is not None:
        out[LK.f9100Count] = f9
    if type is not None:
        out[LK.locationType] = type
    if longitude is not None:
        out[CK.longitude] = longitude
    if latitude is not None:
        out[CK.latitude] = latitude
    return out


def build_distance_cache(
    locations: Dict[str, Dict], generalData: Dict
) -> Dict[str, Dict]:
    keys = []
    lats = []
    longs = []
    willingnessToTravelInMeters = generalData[GK.willingnessToTravelInMeters]
    way_too_far = 1.0
    distance_cache: Dict[str, Dict] = {}
    for key, location in locations.items():
        keys.append(key)
        distance_cache[key] = {}
        lats.append(location[CK.latitude])
        longs.append(location[CK.longitude])
    for i in range(len(lats) - 1):
        for j in range(i + 1, len(lats)):
            abc = abs_angle_change(lats[i], longs[i], lats[j], longs[j])
            if abc > way_too_far:  # very rough distance limit
                continue
            distance = distanceBetweenPoint(lats[i], longs[i], lats[j], longs[j])
            if distance < willingnessToTravelInMeters:
                distance_cache[keys[i]][keys[j]] = distance
                distance_cache[keys[j]][keys[i]] = distance
            else:
                way_too_far = min(way_too_far, 10.0 * abc)
    return distance_cache
