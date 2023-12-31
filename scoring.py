import math
import numpy as np
import uuid

from data_keys import (
    LocationKeys as LK,
    CoordinateKeys as CK,
    GeneralKeys as GK,
    ScoringKeys as SK,
    HotspotKeys as HK,
    MapNames as MN,
    MapKeys as MK,
)
from helper import abs_angle_change, distanceBetweenPoint

from settings import Settings


def calculateScore(
    mapName,
    solution,
    change,
    mapEntity,
    generalData,
    distance_cache,
    sandbox_names=None,
    inverse_sandbox_names=None,
    skip_validation=False,
    round_total=False,
    hotspot_footfall_cache=None,
):
    scoredSolution = {
        SK.gameId: str(uuid.uuid4()),
        SK.mapName: mapName,
        LK.locations: {},
        SK.gameScore: {SK.co2Savings: 0.0, SK.totalFootfall: 0.0},
        SK.totalRevenue: 0.0,
        SK.totalLeasingCost: 0.0,
        SK.totalF3100Count: 0,
        SK.totalF9100Count: 0,
    }

    if mapName not in [MN.sSandbox, MN.gSandbox]:
        locationListNoRefillStation = {}
        for key in mapEntity[LK.locations]:
            loc = mapEntity[LK.locations][key]
            f3_count = 0
            f9_count = 0
            if key in solution[LK.locations]:
                loc_player = solution[LK.locations][key]
                f3_count = loc_player[LK.f3100Count]
                f9_count = loc_player[LK.f9100Count]
            if key in change:
                f3_count += change[key][LK.f3100Count]
                f9_count += change[key][LK.f9100Count]
            f3_count = min(Settings.max_stations, max(0, f3_count))
            f9_count = min(Settings.max_stations, max(0, f9_count))

            if f3_count > 0 or f9_count > 0:
                scoredSolution[LK.locations][key] = {
                    LK.locationName: loc[LK.locationName],
                    LK.locationType: loc[LK.locationType],
                    CK.latitude: loc[CK.latitude],
                    CK.longitude: loc[CK.longitude],
                    LK.footfall: loc[LK.footfall],
                    LK.f3100Count: f3_count,
                    LK.f9100Count: f9_count,
                    LK.salesVolume: loc[LK.salesVolume]
                    * generalData[GK.refillSalesFactor],
                    LK.salesCapacity: f3_count
                    * generalData[GK.f3100Data][GK.refillCapacityPerWeek]
                    + f9_count * generalData[GK.f9100Data][GK.refillCapacityPerWeek],
                    LK.leasingCost: f3_count
                    * generalData[GK.f3100Data][GK.leasingCostPerWeek]
                    + f9_count * generalData[GK.f9100Data][GK.leasingCostPerWeek],
                }

                if scoredSolution[LK.locations][key][LK.salesCapacity] <= 0:
                    raise SystemExit(
                        f"You are not allowed to submit locations with no refill stations. Remove or alter location: {scoredSolution[LK.locations][key][LK.locationName]}"
                    )
            else:
                locationListNoRefillStation[key] = {
                    LK.locationName: loc[LK.locationName],
                    LK.locationType: loc[LK.locationType],
                    CK.latitude: loc[CK.latitude],
                    CK.longitude: loc[CK.longitude],
                    LK.footfall: loc[LK.footfall],
                    LK.salesVolume: loc[LK.salesVolume]
                    * generalData[GK.refillSalesFactor],
                }

        if not scoredSolution[LK.locations]:
            raise SystemExit(
                f"Error: No valid locations with refill stations were placed for map: {mapName}"
            )

        scoredSolution[LK.locations] = distributeSales(
            scoredSolution[LK.locations],
            locationListNoRefillStation,
            generalData,
            distance_cache,
        )
    else:
        if not skip_validation:
            sandboxValidation(mapEntity, solution, change, sandbox_names)
        scoredSolution[LK.locations] = initiateSandboxLocations(
            scoredSolution[LK.locations],
            generalData,
            solution,
            change,
            distance_cache,
            sandbox_names,
            inverse_sandbox_names,
        )
        scoredSolution[LK.locations] = calculateFootfall(
            scoredSolution[LK.locations],
            mapEntity,
            inverse_sandbox_names,
            hotspot_footfall_cache,
        )

    scoredSolution[LK.locations] = divideFootfall(
        scoredSolution[LK.locations],
        generalData,
        distance_cache,
        sandbox_names,
        inverse_sandbox_names,
    )

    for key in scoredSolution[LK.locations]:
        loc = scoredSolution[LK.locations][key]
        loc[LK.salesVolume] = round(loc[LK.salesVolume], 0)
        sales = loc[LK.salesVolume]

        if loc[LK.footfall] <= 0 and mapName in [MN.sSandbox, MN.gSandbox]:
            sales = 0

        if loc[LK.salesCapacity] < loc[LK.salesVolume]:
            sales = loc[LK.salesCapacity]

        loc[LK.revenue] = sales * generalData[GK.refillUnitData][GK.profitPerUnit]
        loc[SK.earnings] = loc[LK.revenue] - loc[LK.leasingCost]

        scoredSolution[SK.totalF3100Count] += scoredSolution[LK.locations][key][
            LK.f3100Count
        ]
        scoredSolution[SK.totalF9100Count] += scoredSolution[LK.locations][key][
            LK.f9100Count
        ]
        loc[LK.co2Savings] = (
            sales
            * (
                generalData[GK.classicUnitData][GK.co2PerUnitInGrams]
                - generalData[GK.refillUnitData][GK.co2PerUnitInGrams]
            )
            - loc[LK.f3100Count] * generalData[GK.f3100Data][GK.staticCo2]
            - loc[LK.f9100Count] * generalData[GK.f9100Data][GK.staticCo2]
        )
        scoredSolution[SK.gameScore][SK.co2Savings] += loc[LK.co2Savings] / 1000

        scoredSolution[SK.totalRevenue] += (
            sales * generalData[GK.refillUnitData][GK.profitPerUnit]
        )

        scoredSolution[SK.totalLeasingCost] += scoredSolution[LK.locations][key][
            LK.leasingCost
        ]

        scoredSolution[SK.gameScore][SK.totalFootfall] += (
            scoredSolution[LK.locations][key][LK.footfall] / 1000
        )

    if round_total:  # why would I want a round total???
        scoredSolution[SK.totalRevenue] = round(scoredSolution[SK.totalRevenue], 2)

        scoredSolution[SK.gameScore][SK.co2Savings] = round(
            scoredSolution[SK.gameScore][SK.co2Savings], 2
        )
        scoredSolution[SK.gameScore][SK.totalFootfall] = round(
            scoredSolution[SK.gameScore][SK.totalFootfall], 4
        )
    else:
        scoredSolution[SK.totalRevenue] = scoredSolution[SK.totalRevenue]

        scoredSolution[SK.gameScore][SK.co2Savings] = scoredSolution[SK.gameScore][
            SK.co2Savings
        ]
        scoredSolution[SK.gameScore][SK.totalFootfall] = scoredSolution[SK.gameScore][
            SK.totalFootfall
        ]

    scoredSolution[SK.gameScore][SK.earnings] = (
        scoredSolution[SK.totalRevenue] - scoredSolution[SK.totalLeasingCost]
    ) / 1000

    if round_total:  # why would I want a round total???
        scoredSolution[SK.gameScore][SK.total] = round(
            (
                scoredSolution[SK.gameScore][SK.co2Savings]
                * generalData[GK.co2PricePerKiloInSek]
                + scoredSolution[SK.gameScore][SK.earnings]
            )
            * (1 + scoredSolution[SK.gameScore][SK.totalFootfall]),
            2,
        )
    else:
        scoredSolution[SK.gameScore][SK.total] = (
            scoredSolution[SK.gameScore][SK.co2Savings]
            * generalData[GK.co2PricePerKiloInSek]
            + scoredSolution[SK.gameScore][SK.earnings]
        ) * (1 + scoredSolution[SK.gameScore][SK.totalFootfall])

    return scoredSolution


def distributeSales(with_, without, generalData, distance_cache):
    for key_without in without:
        nearby = distance_cache.get(key_without)
        distributeSalesTo = {k: d for k, d in nearby.items() if k in with_}

        loc_without = without[key_without]

        total = 0
        if distributeSalesTo:
            for key_temp in distributeSalesTo:
                distributeSalesTo[key_temp] = (
                    math.pow(
                        generalData[GK.constantExpDistributionFunction],
                        generalData[GK.willingnessToTravelInMeters]
                        - distributeSalesTo[key_temp],
                    )
                    - 1
                )
                total += distributeSalesTo[key_temp]

            for key_temp in distributeSalesTo:
                with_[key_temp][LK.salesVolume] += (
                    distributeSalesTo[key_temp]
                    / total
                    * generalData[GK.refillDistributionRate]
                    * loc_without[LK.salesVolume]
                )

    return with_


def calculateFootfall(
    locations, mapEntity, inverse_sandbox_names, hotspot_footfall_cache
):
    maxFootfall = 0
    way_too_far = 10.0
    guts_multiplier = 10.0
    for keyLoc in locations:
        loc = locations[keyLoc]
        isn_key = inverse_sandbox_names[keyLoc]
        if isn_key not in hotspot_footfall_cache:
            increase = 0
            for hotspot in mapEntity[HK.hotspots]:
                abc = abs_angle_change(
                    hotspot[CK.latitude],
                    hotspot[CK.longitude],
                    loc[CK.latitude],
                    loc[CK.longitude],
                )
                if abc > way_too_far:
                    continue
                distanceInMeters = distanceBetweenPoint(
                    hotspot[CK.latitude],
                    hotspot[CK.longitude],
                    loc[CK.latitude],
                    loc[CK.longitude],
                )

                maxSpread = hotspot[HK.spread]
                if distanceInMeters <= maxSpread:
                    val = hotspot[LK.footfall] * (1 - (distanceInMeters / maxSpread))
                    increase += val / 10
                else:
                    way_too_far = min(way_too_far, guts_multiplier * abc)
            hotspot_footfall_cache[isn_key] = increase
        loc[LK.footfall] += hotspot_footfall_cache[isn_key]
        if maxFootfall < loc[LK.footfall]:
            maxFootfall = loc[LK.footfall]

    if maxFootfall > 0:
        for keyLoc in locations:
            loc = locations[keyLoc]
            if loc[LK.footfall] > 0:
                loc[LK.footfallScale] = int(loc[LK.footfall] / maxFootfall * 10)
                if loc[LK.footfallScale] < 1:
                    loc[LK.footfallScale] = 1
    return locations


def getSalesVolume(locationType, generalData):
    for key in generalData[GK.locationTypes]:
        locType = generalData[GK.locationTypes][key]
        if locationType == locType[GK.type_]:
            return locType[GK.salesVol]
    return 0


def initiateSandboxLocations(
    locations: list,
    generalData,
    solution,
    change,
    distance_cache,
    sandbox_names,
    inverse_sandbox_names,
):
    def generate_locations():
        for k, loc in solution[LK.locations].items():
            yield (k, loc)
        for k, loc in change.items():
            if k not in solution[LK.locations]:
                yield (k, loc)

    # get key from the location, but respect changes
    def fetch(locKey, loc, key):
        # loc here skips some lookups but you don't know if it is from solution or change
        if locKey not in change:
            # now we know it is solution loc without any changes
            return loc[key]
        # assume locKey in change, but might not be in solution
        if key in [LK.f3100Count, LK.f9100Count]:
            # counts get summed
            c = 0
            if (
                locKey in solution[LK.locations]
                and key in solution[LK.locations][locKey]
            ):
                c += solution[LK.locations][locKey][key]
            if key in change[locKey]:
                c += change[locKey][key]
            return c
        if key in change[locKey]:
            # not a count so change takes precedence
            return change[locKey][key]
        return solution[LK.locations][locKey][key]

    # sales volumes don't need millions of lookups
    sales_volumes = {}
    for type in generalData[GK.locationTypes].values():
        sales_volumes[type[GK.type_]] = type[GK.salesVol]

    for key, loc in generate_locations():
        loc_type = fetch(key, loc, LK.locationType)
        sv = sales_volumes[loc_type]
        f3 = fetch(key, loc, LK.f3100Count)
        f9 = fetch(key, loc, LK.f9100Count)
        scoredSolution = {
            LK.footfall: 0,
            CK.longitude: fetch(key, loc, CK.longitude),
            CK.latitude: fetch(key, loc, CK.latitude),
            LK.f3100Count: f3,
            LK.f9100Count: f9,
            LK.locationType: loc_type,
            LK.locationName: sandbox_names[key],
            LK.salesVolume: sv,
            LK.salesCapacity: f3 * generalData[GK.f3100Data][GK.refillCapacityPerWeek]
            + f9 * generalData[GK.f9100Data][GK.refillCapacityPerWeek],
            LK.leasingCost: f3 * generalData[GK.f3100Data][GK.leasingCostPerWeek]
            + f9 * generalData[GK.f9100Data][GK.leasingCostPerWeek],
        }
        locations[sandbox_names[key]] = scoredSolution

    for key in locations:
        count = 1

        # for keySurrounding in locations:
        #     if key != keySurrounding:
        #         distance = distanceBetweenPoint(
        #             locations[key][CK.latitude],
        #             locations[key][CK.longitude],
        #             locations[keySurrounding][CK.latitude],
        #             locations[keySurrounding][CK.longitude],
        #         )
        #         if distance < generalData[GK.willingnessToTravelInMeters]:
        #             count += 1
        nearby = [
            k for k in distance_cache[inverse_sandbox_names[key]] if k in sandbox_names
        ]

        # if count != 1 + len(nearby):
        #     print(count, 1 + len(nearby))
        #     print("ERROR")
        #     raise SystemExit("Error")

        count += len(nearby)

        locations[key][LK.salesVolume] = locations[key][LK.salesVolume] / count

    return locations


def divideFootfall(
    locations, generalData, distance_cache, sandbox_names, inverse_sandbox_names
):
    for key in locations:
        if sandbox_names is None:
            count = 1 + len([k for k in distance_cache.get(key) if k in locations])
        else:
            cache_key = inverse_sandbox_names[key]
            count = 1 + len(
                [k for k in distance_cache.get(cache_key) if k in sandbox_names]
            )
        locations[key][LK.footfall] = locations[key][LK.footfall] / count
    return locations


def sandboxValidation(mapEntity, request, change, sandbox_names):
    countGroceryStoreLarge = 0
    countGroceryStore = 0
    countConvenience = 0
    countGasStation = 0
    countKiosk = 0
    maxGroceryStoreLarge = 5
    maxGroceryStore = 20
    maxConvenience = 20
    maxGasStation = 8
    maxKiosk = 3

    totalStores = (
        maxGroceryStoreLarge
        + maxGroceryStore
        + maxConvenience
        + maxGasStation
        + maxKiosk
    )

    numberErrorMsg = f"locationName needs to start with 'location' and followed with a number larger than 0 and less than {totalStores + 1}."

    def generate_locations():
        for k in request[LK.locations]:
            yield k
        for k in change:
            if k not in request[LK.locations]:
                yield k

    for locKey in generate_locations():
        # Validate location name
        name = sandbox_names[locKey]
        if str(name).startswith("location") == False:
            raise SystemExit(f"{numberErrorMsg} {locKey}:{name} is not a valid name")
        loc_num = name[8:]
        if not name:
            raise SystemExit(
                f"{numberErrorMsg} Nothing followed location in the locationName"
            )

        try:
            n = int(loc_num)
            if n <= 0 or n > totalStores:
                raise SystemExit(f"{numberErrorMsg} {n} is not within the constraints")
        except:
            raise SystemExit(f"{numberErrorMsg} {loc_num} is not a number")

        # Validate long and lat
        if locKey in change and CK.latitude in change[locKey]:
            lat = change[locKey][CK.latitude]
        else:
            lat = request[LK.locations][locKey][CK.latitude]
        if (
            mapEntity[MK.border][MK.latitudeMin] > lat
            or mapEntity[MK.border][MK.latitudeMax] < lat
        ):
            raise SystemExit(
                f"Latitude is missing or out of bounds for location : {locKey}:{name}"
            )

        if locKey in change and CK.longitude in change[locKey]:
            long = change[locKey][CK.longitude]
        else:
            long = request[LK.locations][locKey][CK.longitude]
        if (
            mapEntity[MK.border][MK.longitudeMin] > long
            or mapEntity[MK.border][MK.longitudeMax] < long
        ):
            raise SystemExit(
                f"Longitude is missing or out of bounds for location : {locKey}:{name}"
            )

        # Validate locationType
        if locKey in change and LK.locationType in change[locKey]:
            t = change[locKey][LK.locationType]
        else:
            t = request[LK.locations][locKey][LK.locationType]
        if not t:
            raise SystemExit(f"locationType is missing for location) : {locKey}:{name}")
        elif t == "Grocery-store-large":
            countGroceryStoreLarge += 1
        elif t == "Grocery-store":
            countGroceryStore += 1
        elif t == "Convenience":
            countConvenience += 1
        elif t == "Gas-station":
            countGasStation += 1
        elif t == "Kiosk":
            countKiosk += 1
        else:
            raise SystemExit(
                f"locationType --> {t} not valid (check GetGeneralGameData for correct values) for location : {locKey}:{name}"
            )
        # Validate that max number of location is not exceeded
        if (
            countGroceryStoreLarge > maxGroceryStoreLarge
            or countGroceryStore > maxGroceryStore
            or countConvenience > maxConvenience
            or countGasStation > maxGasStation
            or countKiosk > maxKiosk
        ):
            raise SystemExit(
                f"Number of allowed locations exceeded for locationType: {t}"
            )
