import json
from typing import Optional
import requests


from config import LASTFM_API_KEY as API_KEY

# def hoi(
#     username: str, drange: Optional[str] = None
# ) -> str:  # returns json
#     url = None
#     if drange and drange.startswith("http"):
#         url = drange
#     else:
#         preset = f"LAST_{drange}_DAYS" if drange else "ALL"
#         url = f"https://www.last.fm/user/{username}/library/albums?date_preset={preset}"
#         print(url)
#     resp = session.get(url, timeout=TIMEOUT)
#     # get each column of artist name, album name and number of scrobbles
#     data = zip(
#         doc.xpath("//tr/td[@class='chartlist-name']/a"),
#         doc.xpath("//tr/td[@class='chartlist-artist']/a"),
#         doc.xpath("//tr/td/span/a/span[@class='chartlist-count-bar-value']"),
#         doc.xpath("//tr/td[@class='chartlist-index']"),
#     )
#     # Needs to be cacheable so we can not use a generator.
#     return json.dumps(
#         list(
#             x
#             for x in (list(map(lambda e: e.text.strip(), elements)) for elements in data)
#             if int(x[3]) <= MAX_ITEMS  # Do not return the full chartlist.
#         )
#     )

import sys
session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount("https://", a)
API_PERIOD = {
    '': 'overall',
    '7': '7day',
    '30': '1month',
    '90': '3month',
    '180': '6month',
    '365': '12month',
}

def _get_album_stats_api(
    username: str, drange: Optional[str] = None
) -> str:  # returns json
    from scrape import MAX_ITEMS, TIMEOUT
    url = None
    if drange.startswith("http"):
        url = drange
        raise NotImplementedError(f'get album stats api for {drange}')
    elif p := API_PERIOD[drange]:
        url = f"https://ws.audioscrobbler.com/2.0/?method=user.gettopalbums&user={username}&api_key={API_KEY}&period={p}&format=json&limit={MAX_ITEMS}"
        print("Getting " + url)
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        j = resp.json()
        return json.dumps(
            [
                (
                    top['name'],
                    top['artist']['name'],
                    top['playcount'],
                    top['@attr']['rank'],
                )
                for top in j['topalbums']['album']
            ]
        )
