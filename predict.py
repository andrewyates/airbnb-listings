import codecs
import json
import hashlib
import os
import random
import sys

import geopy.distance
import geopy.geocoders
import sklearn.cross_validation
import sklearn.feature_extraction
import sklearn.linear_model
import sklearn.preprocessing

from sklearn.metrics import mean_absolute_error


class Predict:
    def __init__(self):
        self.cache = "cache"
        if not os.path.exists(self.cache):
            os.mkdir(self.cache)

        # require property_type to be Apartment or House
        self.field_restrictions = {'property_type': lambda x: x in set(["Apartment", "House"]),
                                   'price': lambda x: x > 0 and x < 150,
                                   'room_type_category': lambda x: x == 'entire_home'}

        with open('data/wmata_metro_stations.csv') as f:
            self.metro_coords = [(float(lat), float(lng)) for lng, lat in [x.split(",") for x in f.readlines()]]

        with open('data/dc_crime_incidents_2013.csv') as f:
            crime_addresses = [x.split(",")[6].strip() for x in f.readlines()]
        self.crime_coords = self.addresses_to_coords(crime_addresses)

        self.popular_areas = {'1600kst': (38.902533, -77.036364),
                              'dupont': (38.911105, -77.044342),
                              'shaw': (38.914444, -77.021892),
                              'easternmarket': (38.884252, -76.994898)}

    def build_vector(self, l):
        direct_fields = ['instant_bookable', 'has_simplified_booking', 'bedrooms', 'beds',
                         'person_capacity', 'picture_count', 'reviews_count']
        v = {k: float(l[k]) for k in direct_fields if l[k] is not None}

        v['typeis_%s' % l['room_type_category']] = 1.0

        v['distance_to_metro1'], v['distance_to_metro2'] = self.metro_distance(l['lat'], l['lng'], topk=2)

        for name, coord in self.popular_areas.iteritems():
            v['distance_to_%s' % name] = geopy.distance.distance((l['lat'], l['lng']), coord).km

        return v

    def predict_prices(self, listings):
        listings = [l for l in listings if self.valid_listing(l)]
        random.seed(23563987)
        random.shuffle(listings)

        scaler = sklearn.preprocessing.MinMaxScaler()
        allXs = [self.build_vector(l) for l in listings]
        allYs = [l['price'] for l in listings]

        maes = []
        for train_idx, test_idx in sklearn.cross_validation.KFold(len(allXs), n_folds=10):
            v = sklearn.feature_extraction.DictVectorizer(sparse=False)
            trainX = [allXs[i] for i in train_idx]
            trainY = [allYs[i] for i in train_idx]
            trainX = scaler.fit_transform(v.fit_transform(trainX), trainY)

            testX = [allXs[i] for i in test_idx]
            testY = [allYs[i] for i in test_idx]
            testX = scaler.transform(v.transform(testX))

            clf = sklearn.linear_model.Ridge()
            clf.fit(trainX, trainY)
            predY = clf.predict(testX)
            maes.append(mean_absolute_error(predY, testY))

        print "average MAE: %0.1f" % (float(sum(maes)) / len(maes))

    def valid_listing(self, l):
        for k, func in self.field_restrictions.iteritems():
            if not func(l[k]):
                return False

        return True

    def metro_distance(self, lat, lng, topk=2):
        distances = [geopy.distance.distance((lat, lng), metrocoord).km for metrocoord in self.metro_coords]
        return sorted(distances)[:topk]

    def addresses_to_coords(self, addrs):
        cachefn = os.path.join(self.cache, "address_coords.json")

        coordmap = {}
        if os.path.exists(cachefn):
            with open(cachefn) as f:
                try:
                    coordmap = json.load(f)
                except:
                    coordmap = {}

        g = geopy.geocoders.GoogleV3()
        for addr in addrs:
            if addr not in coordmap:
                resp = g.geocode("%s, WASHINGTON, DC" % addr)

                if resp is not None:
                    _, coord = resp
                    coordmap[addr] = coord

                with open(cachefn, 'w') as f:
                    json.dump(coordmap, f)

        return [coordmap[addr] for addr in addrs if coordmap[addr] is not None]

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print >> sys.stderr, "%s: usage: <listings json file>"
        sys.exit(1)

    with codecs.open(sys.argv[1], 'r', encoding='utf-8') as f:
        listings = json.load(f)

    p = Predict()
    p.predict_prices(listings)
