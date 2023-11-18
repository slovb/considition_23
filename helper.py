from data_keys import LocationKeys as LK

from settings import Settings


def bundle(f3=0, f9=0):
    return {
        LK.f3100Count: f3,
        LK.f9100Count: f9,
    }


def apply_change(locations, change, capped=True):
    for key, mod in change.items():
        if key not in locations:
            locations[key] = mod
        else:
            for mkey, mval in mod.items():
                locations[key][mkey] = locations[key][mkey] + mval
            if locations[key][LK.f3100Count] == 0 and locations[key][LK.f9100Count] == 0:
                del locations[key]
    if capped:
        for loc in locations.values():
            for key, val in loc.items():
                if val < 0 or val > Settings.max_stations:
                    loc[key] = min(Settings.max_stations, max(0, val))
