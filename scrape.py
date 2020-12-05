#!/usr/bin/env python
# By Apie
# 2020-12-05
# Script to fetch album stats from last.fm and recalculate them based on track count per album.

# IDEA: use playcount in minutes
# TODO
# use logger for url logging
# switch between all time/last year etc
# heavier caching: db or file

import requests
from lxml import html
from functools import lru_cache
TIMEOUT = 5

@lru_cache()
def get_album_stats(username):
    # url to get album scrobbles for this user off all time
    url = f"https://www.last.fm/user/{username}/library/albums"
    # if username does not exist this will return a 404
    print(url)
    page = requests.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # get each column of artist name, album name and number of scrobbles
    l = zip(
        doc.xpath("//tr/td[@class='chartlist-name']/a"),
        doc.xpath("//tr/td[@class='chartlist-artist']/a"),
        doc.xpath("//tr/td/span/a/span[@class='chartlist-count-bar-value']")
    )
    return (map(lambda e: e.text.strip(), elements) for elements in l)

@lru_cache()
def _get_album_track_count(album_name, artist_name) -> str:
    # TODO what about albums that are detected incorrectly?
    # eg https://www.last.fm/music/Delain/April+Rain is recognized as the single, with only 2 tracks.
    # Maybe always add a cross check to discogs?
    url = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}/{album_name.replace(' ', '+')}"
    print(url)
    page = requests.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # search for: Length ## tracks, ##:##
    try:
        dd = doc.xpath("//dd[@class='catalogue-metadata-description']")[0]
        return dd.text_content().strip().split('tracks')[0].strip()
    except IndexError:
        # TODO add fallback? Discogs or something
        return 12 # Use some average track count


def _get_corrected_stats_for_album(album_stats):
    # fetch the number of tracks on that album
    # calculate the number of album plays
    # return as a list
    album_name, artist_name, scrobble_count = album_stats
    track_count = _get_album_track_count(album_name, artist_name)
    album_scrobble_count = int(scrobble_count) / int(track_count)
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