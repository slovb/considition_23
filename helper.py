from data_keys import (
    CoordinateKeys as CK,
    LocationKeys as LK,
)

from settings import Settings


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


def apply_change(locations, change, capped=True):
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
        for key in to_remove:
            del locations[key]
