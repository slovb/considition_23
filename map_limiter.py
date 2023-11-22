# @frozen
class MapLimiter:
    def __init__(self, latitudeMin, latitudeMax, longitudeMin, longitudeMax):
        self.latitudeMin = latitudeMin
        self.latitudeMax = latitudeMax
        self.longitudeMin = longitudeMin
        self.longitudeMax = longitudeMax

    def latitude(self, latitude):
        return min(self.latitudeMax, max(self.latitudeMin, latitude))

    def longitude(self, longitude):
        return min(self.longitudeMax, max(self.longitudeMin, longitude))
