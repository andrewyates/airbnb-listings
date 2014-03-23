import codecs
import json
import random
import sys
import time

import lxml.html
import requests


class AirbnbScraper:
    def __init__(self, debug=True):
        self.cookies = {}
        self.debug = debug

    def listing_url(self, zipcode, offset):
        return ('https://m.airbnb.com/api/-/v1/listings/search?location=%s&number_of_guests=1&offset=%s&guests=1&items_per_page=20'
                % (zipcode, offset))

    def get(self, url, referer='', min_sleep=30, max_add=120, xhr=False):
        if self.debug:
            print url

        time.sleep(random.randint(0, max_add) + min_sleep)

        headers = {'User-agent': 'Mozilla/5.0 (Linux; U; Android 2.3; en-us) AppleWebKit/999+ (KHTML, like Gecko) Safari/999.9',
                   'referer': referer}
        if xhr:
            headers['x-requested-with'] = 'XMLHttpRequest'

        r = requests.get(url, headers=headers, cookies=self.cookies)
        self.cookies = r.cookies

        return r

    def get_listing_calendar(self, lid):
        cal = {}

        year = 2014
        for month in [4, 5]:
            url = "https://www.airbnb.com/rooms/calendar_tab_inner2/%s?cal_month=%s&cal_year=%s&currency=USD" % (lid, month, year)
            r = self.get(url, referer='https://www.airbnb.com/listings/%s' % lid, xhr=True)
            dom = lxml.html.fromstring(r.content)

            inMonth = False
            for td in dom.cssselect("td"):
                spans = td.cssselect("span")
                if len(spans) != 1:
                    print >> sys.stderr, "error: unsure how to deal with HTML (line %s) containing != 1 spans: %s" % (td.sourceline,
                                                                                                                      r.content)
                    sys.exit(1)

                day = int(spans[0].text)
                if day < 1 or day > 31:
                    print >> sys.stderr, "error: parsed invalid date from HTML (line %s): %s" % (td.sourceline, r.content)
                    sys.exit(1)

                if day == 1:
                    if inMonth:
                        inMonth = False
                    else:
                        inMonth = True

                if inMonth:
                    classes = td.get("class").split(" ")
                    if "available" in classes:
                        available = True
                    elif "unavailable" in classes:
                        available = False
                    else:
                        print >> sys.stderr, "error: listing is neither available or unavailable: %s" % classes
                        sys.exit(1)

                    cal[(month, day, year)] = available

        return cal

    def crawl(self, zipcode):
        offset = 0
        fields = ['id', 'price', 'lat', 'lng', 'instant_bookable', 'has_simplified_booking', 'bedrooms', 'beds',
                  'person_capacity', 'picture_count', 'property_type', 'room_type', 'room_type_category', 'reviews_count']

        count = 999
        listings = []
        crawled_listings = set()
        while len(listings) < count and offset < count:
            r = self.get(self.listing_url(zipcode, offset), referer='https://m.airbnb.com/s/%s' % zipcode)

            try:
                js = json.loads(r.content)
                count = js['listings_count']

                if len(js['listings']) == 0:
                    break
                else:
                    new_listings = [{k: listing['listing'].get(k, None) for k in fields} for listing in js['listings']
                                    if listing['listing']['id'] not in crawled_listings]
                    for new_listing in new_listings:
                        new_listing['calendar'] = self.get_listing_calendar(new_listing['id'])

                    listings.extend([listing for listing in new_listings if listing['id'] not in crawled_listings])
                    crawled_listings.update(listing['id'] for listing in new_listings)

                offset += 20
                if self.debug:
                    print "new offset", offset

            except ValueError as e:
                print >> sys.stderr, 'received ValueError:', e
                print >> sys.stderr, 'error: could not parse response'
                sys.exit(1)

        with codecs.open('listings.json', 'w', encoding='utf-8') as f:
            json.dump(listings, f)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print >> sys.stderr, "%s: usage: <zip code>" % sys.argv[0]

    ab = AirbnbScraper()
    ab.crawl(sys.argv[1])
