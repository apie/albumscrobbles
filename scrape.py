#!/usr/bin/env python
# By Apie
# 2020-12-05
# Script to fetch album stats from last.fm and recalculate them based on track count per album.

# Caching policy:
# Track count: forever
# all time stats: 2 months
# 365: 30 days
# 180: 15 days
#  90:  7 days
#  30:  3 days
#   7:  1 day

import requests
from lxml import html
from file_cache import file_cache_decorator

TIMEOUT = 8

session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount('https://', a)

def get_album_stats(username):
    # TODO make possible to get stats of other time frames
    # url to get album scrobbles for this user off all time
    url = f"https://www.last.fm/user/{username}/library/albums"
    # if username does not exist this will return a 404
    print(url)
    page = session.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # get each column of artist name, album name and number of scrobbles
    l = zip(
        doc.xpath("//tr/td[@class='chartlist-name']/a"),
        doc.xpath("//tr/td[@class='chartlist-artist']/a"),
        doc.xpath("//tr/td/span/a/span[@class='chartlist-count-bar-value']")
    )
    return (map(lambda e: e.text.strip(), elements) for elements in l)

@file_cache_decorator()
def _get_album_track_count(artist_name, album_name) -> str:
    # TODO what about albums that are detected incorrectly?
    # eg https://www.last.fm/music/Delain/April+Rain is recognized as the single, with only 2 tracks.
    # Maybe always add a cross check to discogs?
    url = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}/{album_name.replace(' ', '+')}"
    print(url)
    page = session.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # search for: <dt>Length</dt> <dd>## tracks, ##:##</dd>
    try:
        dd = doc.xpath("//dt[@class='catalogue-metadata-heading'][contains(text(),'Length')]/following-sibling::dd")[0]
        return dd.text_content().strip().split('track')[0].strip()
    except IndexError:
        # TODO add fallback? Discogs or something
        return str(12) # Use some average track count


def _get_corrected_stats_for_album(album_stats):
    # fetch the number of tracks on that album
    # calculate the number of album plays
    # return as a list
    album_name, artist_name, scrobble_count = album_stats
    track_count = _get_album_track_count(artist_name, album_name)
    album_scrobble_count = int(scrobble_count.replace(',', '')) // int(track_count)
    return album_name, artist_name, scrobble_count, track_count, album_scrobble_count

def correct_album_stats(stats):
    return (
        _get_corrected_stats_for_album(stat)
        for stat in stats
    )

def username_exists(username):
    resp = session.head(f"https://www.last.fm/user/{username}")
    return resp.status_code == 200

if __name__ == "__main__":
    from pprint import pprint
    from sys import argv
    if len(argv) == 1:
        raise Exception('Give username as first argument')
    stats = get_album_stats(argv[1])
    corrected = correct_album_stats(stats)
    print(f'Album stats for {argv[1]}')
    print(('Album', 'Artist', 'Track playcount', 'Album track count', 'Album plays'))
    pprint(sorted(list(corrected), key=lambda x: x[4]))
