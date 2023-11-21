from dataclasses import dataclass
from data_keys import (
    CoordinateKeys as CK,
    GeneralKeys as GK,
    LocationKeys as LK,
)

from settings import Settings


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


def apply_change(locations, change, capped=True, no_remove=False):
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


def bundle(f3=None, f9=None, type=None, longitude=None, latitude=None):
    out = {}
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


def temporary_names(solution, change):
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
