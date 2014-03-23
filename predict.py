import codecs
import json
import random
import sys

import sklearn.cross_validation
import sklearn.feature_extraction
import sklearn.linear_model
import sklearn.preprocessing

from sklearn.metrics import mean_absolute_error


class Predict:
    def __init__(self):
        # require property_type to be Apartment or House
        self.field_restrictions = {'property_type': lambda x: x in set(["Apartment", "House"])}
                                  # 'room_type_category': lambda x: x == 'entire_home'}}

    def build_vector(self, l):
        direct_fields = ['instant_bookable', 'has_simplified_booking', 'bedrooms', 'beds',
                         'person_capacity', 'picture_count', 'reviews_count']
        v = {k: float(l[k]) for k in direct_fields if l[k] is not None}
        v['typeis_%s' % l['room_type_category']] = 1.0

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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print >> sys.stderr, "%s: usage: <listings json file>"
        sys.exit(1)

    with codecs.open(sys.argv[1], 'r', encoding='utf-8') as f:
        listings = json.load(f)

    p = Predict()
    p.predict_prices(listings)
