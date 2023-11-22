from typing import Any, Dict, Optional
from data_keys import (
    CoordinateKeys as CK,
    LocationKeys as LK,
)

from settings import Settings


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
