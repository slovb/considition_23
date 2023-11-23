# @frozen
class MapLimiter:
    def __init__(
        self,
        latitudeMin: float,
        latitudeMax: float,
        longitudeMin: float,
        longitudeMax: float,
    ) -> None:
        self.latitudeMin = latitudeMin
        self.latitudeMax = latitudeMax
        self.longitudeMin = longitudeMin
        self.longitudeMax = longitudeMax
        self.latitudeDiff = latitudeMax - latitudeMin
        self.longitudeDiff = longitudeMax - longitudeMin

    def latitude(self, latitude: float) -> float:
        return min(self.latitudeMax, max(self.latitudeMin, latitude))

    def longitude(self, longitude: float) -> float:
        return min(self.longitudeMax, max(self.longitudeMin, longitude))
