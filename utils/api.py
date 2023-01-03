import json
import requests
from typing import Optional


from config import LASTFM_API_KEY as API_KEY

session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount("https://", a)

API_PERIOD = {
    None: 'overall',
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
    if drange and drange.startswith("http"):
        url = drange + f'&limit={MAX_ITEMS}&api_key={API_KEY}'
        print("Getting " + url)
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        j = resp.json()
        # Dump as json so we can cache it to disk
        return json.dumps(
            [
                (
                    top['name'],
                    top['artist']['#text'],
                    top['playcount'],
                    top['@attr']['rank'],
                )
                for top in j['weeklyalbumchart']['album']
            ]
        )
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


def _get_user_info(username):
    url = f'http://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={username}&api_key={API_KEY}&format=json'
    print("Getting " + url)
    from scrape import TIMEOUT
    resp = session.get(url, timeout=TIMEOUT)
    if resp.status_code == 404:
        return ''
    # Dump json as text so we can cache it to disk
    return resp.text
