import sys
import json
import requests
from typing import Optional


from config import LASTFM_API_KEY as API_KEY

session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount("https://", a)
API_PERIOD = {
    None: 'overall',
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
    if drange and drange.startswith("http"):
        url = drange
        raise NotImplementedError(f'get album stats api for {drange}')
    elif p := API_PERIOD[drange]:
        url = f"https://ws.audioscrobbler.com/2.0/?method=user.gettopalbums&user={username}&api_key={API_KEY}&period={p}&format=json&limit={MAX_ITEMS}"
        print("Getting " + url)
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        j = resp.json()
        # Dump as json so we can cache it to disk
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
