#!/usr/bin/env python
# By Apie
# 2020-12-05
# Script to fetch album stats from last.fm and recalculate them based on track count per album.

# IDEA: use playcount in minutes
# TODO
# use logger for url logging
# switch between all time/last year etc

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
from functools import lru_cache
from pathlib import Path
TIMEOUT = 8
USE_FILE_CACHE = True

session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount('https://', a)

def get_filename(*args):
    return '-'.join(arg.replace('/','-') for arg in args)

def get_from_cache(*args, func, keep_days=None) -> str:
    #TODO implement keep_days
    print(f"getting {func} from cache: {args=} {keep_days=}")
    with open(f"/tmp/albumscrobbles/{func}/{get_filename(*args)}") as f:
        return f.read()

def update_cache(*args, func, result: str):
    assert isinstance(result, str), f'Cache can only be used for string results! Not for {result}'
    print(f"updating {func} in cache: {args=} {result=}")
    path = Path(f"/tmp/albumscrobbles/{func}")
    path.mkdir(parents=True, exist_ok=True)
    with open(path / Path(get_filename(*args)), "w") as f:
        f.write(result)
    print('updated cache')

def file_cache_decorator(keep_days=None):
    def inner(func):
        def wrapper(*args, **kwargs):
            if not USE_FILE_CACHE:
                return func(*args, **kwargs)
            try:
                return get_from_cache(*args, **kwargs, func=func.__name__, keep_days=keep_days)
            except FileNotFoundError:
                result = func(*args, **kwargs)
                update_cache(*args, **kwargs, func=func.__name__, result=result)
                return result
        return wrapper
    return inner

@lru_cache()
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

@lru_cache()
@file_cache_decorator()
def _get_album_track_count(artist_name, album_name) -> str:
    # TODO what about albums that are detected incorrectly?
    # eg https://www.last.fm/music/Delain/April+Rain is recognized as the single, with only 2 tracks.
    # Maybe always add a cross check to discogs?
    url = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}/{album_name.replace(' ', '+')}"
    print(url)
    page = session.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # search for: Length ## tracks, ##:##
    try:
        dd = doc.xpath("//dd[@class='catalogue-metadata-description']")[0]
        return dd.text_content().strip().split('tracks')[0].strip()
    except IndexError:
        # TODO add fallback? Discogs or something
        return str(12) # Use some average track count


def _get_corrected_stats_for_album(album_stats):
    # fetch the number of tracks on that album
    # calculate the number of album plays
    # return as a list
    album_name, artist_name, scrobble_count = album_stats
    track_count = _get_album_track_count(artist_name, album_name)
    album_scrobble_count = int(scrobble_count) // int(track_count)
    return album_name, artist_name, scrobble_count, track_count, album_scrobble_count

def correct_album_stats(stats):
    return (
        _get_corrected_stats_for_album(stat)
        for stat in stats
    )

# print(get_album_track_count("TRON: Legacy", "Daft Punk"))
# print(list(next(get_album_stats('casparv'))))
# print(get_corrected_album_stats(['TRON: Legacy', 'Daft Punk', '925']))
# for stat in get_album_stats('casparv'):
    # print('-'*10)
    # stat = list(stat)
    # print(stat)
    # print(get_corrected_stats_for_album(stat))
from pprint import pprint
stats = get_album_stats('casparv')
corrected = correct_album_stats(stats)
pprint(sorted(list(corrected), key=lambda x: x[4]))
stats = get_album_stats('denick')
corrected = correct_album_stats(stats)
pprint(sorted(list(corrected), key=lambda x: x[4]))