import itertools
from typing import Dict, Tuple
from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    HotspotKeys as HK,
    LocationKeys as LK,
)
from helper import abs_angle_change, bundle, distanceBetweenPoint
from map_limiter import MapLimiter
from settings import Settings, KW


def build_hotspot_cache(mapEntity: Dict, generalData: Dict) -> Dict:
    hotspots = mapEntity[HK.hotspots]
    hotspot_cache = {}
    keys = []
    way_too_far = 10.0
    guts_multiplier = 10.0
    willingnessToTravelInMeters = generalData[GK.willingnessToTravelInMeters]
    for key, hotspot in enumerate(hotspots):
        keys.append(key)
        hotspot_cache[key] = hotspot
        hotspot_cache[key][KW.nearby] = {}
    for i, i_key in enumerate(keys[:-1]):
        i_lat = hotspot_cache[i_key][CK.latitude]
        i_long = hotspot_cache[i_key][CK.longitude]
        i_spread = hotspot_cache[i_key][HK.spread]
        for j_key in keys[i + 1 :]:
            j_lat = hotspot_cache[j_key][CK.latitude]
            j_long = hotspot_cache[j_key][CK.longitude]
            j_spread = hotspot_cache[j_key][HK.spread]
            abc = abs_angle_change(i_lat, i_long, j_lat, j_long)
            if abc > way_too_far:  # very rough distance limit
                continue
            distance = distanceBetweenPoint(i_lat, i_long, j_lat, j_long)
            # if distance < i_spread + j_spread + willingnessToTravelInMeters:
            # if distance < max(i_spread, j_spread):
            if distance < max(i_spread + j_spread, willingnessToTravelInMeters):
                hotspot_cache[i_key][KW.nearby][j_key] = distance
                hotspot_cache[j_key][KW.nearby][i_key] = distance
            else:
                way_too_far = min(way_too_far, guts_multiplier * abc)
    return hotspot_cache


def find_possible_locations(
    hotspot_cache: Dict, map_limiter: MapLimiter
) -> Dict[str, Dict]:
    locations = {}
    i = 1
    taken = set()
    tkey = lambda x: int(x * Settings.granularity)

    def adder(i: int, latitude: float, longitude: float, name: str) -> int:
        la = map_limiter.latitude(latitude)
        lo = map_limiter.longitude(longitude)
        kk = (tkey(la), tkey(lo))
        if kk not in taken:
            locations[f"c_{name}_{i}"] = bundle(
                latitude=la,
                longitude=lo,
            )
            taken.add(kk)
            return i + 1
        return i

    w = lambda spread, footfall: spread * footfall

    for hotspot in hotspot_cache.values():
        hotspot_la = hotspot[CK.latitude]
        hotspot_lo = hotspot[CK.longitude]
        hotspot_w = w(hotspot[HK.spread], hotspot[LK.footfall])

        # add the hotspot as a location
        i = adder(i, hotspot_la, hotspot_lo, "hotspot")

        # start collecting a cluster node
        cluster_la = hotspot_la * hotspot_w
        cluster_lo = hotspot_lo * hotspot_w
        cluster_w = hotspot_w

        for neighbor_key in hotspot[KW.nearby]:
            neighbor = hotspot_cache[neighbor_key]
            neighbor_la = neighbor[CK.latitude]
            neighbor_lo = neighbor[CK.longitude]
            neighbor_w = w(neighbor[HK.spread], neighbor[LK.footfall])

            # add the weighted average of the two points
            avg_la = (hotspot_la * hotspot_w + neighbor_la * neighbor_w) / (
                hotspot_w + neighbor_w
            )
            avg_lo = (hotspot_lo * hotspot_w + neighbor_lo * neighbor_w) / (
                hotspot_w + neighbor_w
            )
            i = adder(i, avg_la, avg_lo, "between")

            # increase the clusterpoint
            cluster_la += neighbor_la * neighbor_w
            cluster_lo += neighbor_lo * neighbor_w
            cluster_w += neighbor_w

        # add the clusterpoint
        cluster_la = cluster_la / cluster_w
        cluster_lo = cluster_lo / cluster_w
        i = adder(i, cluster_la, cluster_lo, "cluster")

    print(f"{len(locations)} candidates")
    return locations


# great but expensive
# def find_possible_locations(
#     hotspot_cache: Dict, map_limiter: MapLimiter
# ) -> Dict[str, Dict]:
#     locations = {}
#     i = 1
#     taken = set()
#     tkey = lambda x: int(x * Settings.granularity)

#     def adder(i: int, latitude: float, longitude: float, name: str) -> int:
#         la = map_limiter.latitude(latitude)
#         lo = map_limiter.longitude(longitude)
#         kk = (tkey(la), tkey(lo))
#         if kk not in taken:
#             locations[f"c_{name}_{i}"] = bundle(
#                 latitude=la,
#                 longitude=lo,
#             )
#             taken.add(kk)
#             return i + 1
#         return i

#     w = lambda spread, footfall: spread * footfall

#     for hotspot in hotspot_cache.values():
#         hotspot_la = hotspot[CK.latitude]
#         hotspot_lo = hotspot[CK.longitude]
#         hotspot_w = w(hotspot[HK.spread], hotspot[LK.footfall])

#         # add the hotspot as a location
#         i = adder(i, hotspot_la, hotspot_lo, "hotspot")

#         nearby: Dict[str, Dict] = hotspot[KW.nearby]
#         for keys in itertools.combinations(nearby.keys(), 2):
#             tri_la = hotspot_la * hotspot_w
#             tri_lo = hotspot_lo * hotspot_w
#             tri_w = hotspot_w
#             for key in keys:
#                 neighbor = hotspot_cache[key]
#                 neighbor_w = w(neighbor[HK.spread], neighbor[LK.footfall])
#                 tri_la += neighbor[CK.latitude] * neighbor_w
#                 tri_lo += neighbor[CK.longitude] * neighbor_w
#                 tri_w += neighbor_w
#             i = adder(i, tri_la / tri_w, tri_lo / tri_w, "triangle")

#     print(f"{len(locations)} candidates")
#     return locations


def temporary_names(
    solution: Dict, change: Dict[str, Dict]
) -> Tuple[Dict[str, str], Dict[str, str]]:
    names = {}
    inverse = {}
    i = 1
    for key in solution[LK.locations]:
        name = f"location{i}"
        names[key] = name
        inverse[name] = key
        i += 1
    for key in change:
        if key not in solution[LK.locations]:
            name = f"location{i}"
            names[key] = name
            inverse[name] = key
            i += 1
    return names, inverse
