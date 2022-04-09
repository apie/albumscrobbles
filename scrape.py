#!/usr/bin/env python
# By Apie
# 2020-12-05
# Script to fetch album stats from last.fm and recalculate them based on track count per album.

# Caching policy:
# Track count and blast from the past: forever
# all time: 1 year
# 365, 180: 1 month
# 90, 30, 7:  1 day

import base64
import json
import requests
import re
from lxml import html
from functools import lru_cache
from typing import Optional, Iterable, Dict, Tuple
from random import randint
from datetime import datetime
from dateutil.relativedelta import relativedelta
from urllib.parse import quote_plus

from file_cache import file_cache_decorator, binary_file_cache_decorator

TIMEOUT = 8
MAX_ITEMS = 20
PAGE_SIZE = 50

session = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
session.mount("https://", a)


@binary_file_cache_decorator(return_path=True)
def cache_binary_url_and_return_path(url: str) -> bytes:
    print("Getting " + url)
    return session.get(url, timeout=TIMEOUT).content


@file_cache_decorator(keep_days=1)
def get_album_stats_cached_one_day(username, drange=None):
    return _get_album_stats(username, drange)


@file_cache_decorator(keep_days=30)
def get_album_stats_cached_one_month(username, drange=None):
    return _get_album_stats(username, drange)


@file_cache_decorator(keep_days=365)
def get_album_stats_cached_one_year(username, drange=None):
    return _get_album_stats(username, drange)


@file_cache_decorator()
def get_album_stats_cached(username, drange=None):
    return _get_album_stats(username, drange)


def get_album_stats(username: str, drange: Optional[str] = None) -> Iterable:
    if drange and drange.startswith("http"):
        # blast from the past. cache forever
        retval = get_album_stats_cached(username, drange)
    elif drange and int(drange) < 180:
        retval = get_album_stats_cached_one_day(username, drange)
    elif drange and int(drange) <= 365:
        retval = get_album_stats_cached_one_month(username, drange)
    else:
        retval = get_album_stats_cached_one_year(username, drange)
    return json.loads(retval)


def get_random_interval_from_library(username: str) -> str:
    # select a random interval from the library
    user_start_year = get_username_start_year(username)
    today = datetime.today()
    current_year = today.year

    rand_year = randint(int(user_start_year), current_year - 1)
    rand_month = randint(1, 12)
    interval_type = randint(1, 3)
    if interval_type == 1:
        name = "random month"
        start_date = datetime(year=rand_year, month=rand_month, day=1)
        end_date = start_date + relativedelta(months=1)
        date_str = start_date.strftime("%B %Y")
    elif interval_type == 2:
        name = "this month in history"
        start_date = datetime(year=rand_year, month=today.month, day=1)
        end_date = start_date + relativedelta(months=1)
        date_str = start_date.strftime("%B %Y")
    else:
        name = "random year"
        start_date = datetime(year=rand_year, month=1, day=1)
        end_date = start_date + relativedelta(years=1)
        date_str = start_date.strftime("%Y")
    print(f"Trying {name}...")
    url = f"https://www.last.fm/user/{username}/library/albums?from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}"
    print(url)
    return name, date_str, url


def _get_album_stats(
    username: str, drange: Optional[str] = None
) -> str:  # returns json
    print(f"_get_album_stats {username} {drange}")
    assert (
        MAX_ITEMS <= PAGE_SIZE
    ), f"{MAX_ITEMS} items requested, this is not yet supported since paging is not yet implemented"
    url = None
    if drange and drange.startswith("http"):
        url = drange
    else:
        preset = f"LAST_{drange}_DAYS" if drange else "ALL"
        url = f"https://www.last.fm/user/{username}/library/albums?date_preset={preset}"
        print(url)
    page = session.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # get each column of artist name, album name and number of scrobbles
    data = zip(
        doc.xpath("//tr/td[@class='chartlist-name']/a"),
        doc.xpath("//tr/td[@class='chartlist-artist']/a"),
        doc.xpath("//tr/td/span/a/span[@class='chartlist-count-bar-value']"),
        doc.xpath("//tr/td[@class='chartlist-index']"),
    )
    # Needs to be cacheable so we can not use a generator.
    return json.dumps(
        list(
            x
            for x in (list(map(lambda e: e.text.strip(), elements)) for elements in data)
            if int(x[3]) <= MAX_ITEMS  # Do not return the full chartlist.
        )
    )


@file_cache_decorator()
def _get_album_details(artist_name, album_name) -> str:
    # What about albums that are detected incorrectly?
    # eg https://www.last.fm/music/Delain/April+Rain is recognized as the single, with only 2 tracks.
    # Maybe always add a cross check to discogs?
    # For now: ignore 1-2 track albums for now and just return the average.
    artist_name = artist_name.replace('+', '%2B')  # Fix for Cuby+Blizzards. + Needs to be encoded twice.
    url = "https://www.last.fm/music/" + quote_plus(artist_name) + "/" + quote_plus(album_name)
    print("Getting " + url)
    page = session.get(url, timeout=TIMEOUT).text
    doc = html.fromstring(page)
    # search for: <dt>Length</dt> <dd>## tracks, ##:##</dd>
    try:
        dd = doc.xpath(
            "//dt[@class='catalogue-metadata-heading'][contains(text(),'Length')]/following-sibling::dd"
        )[0]
        track_count = dd.text_content().strip().split("track")[0].strip()
        assert track_count.isnumeric()
        assert int(track_count) > 2, "Probably not a real album"
    except (IndexError, AssertionError):
        # TODO add fallback? Discogs or something
        track_count = str(12)  # Use some average track count

    # search for: <a class="cover-art"><img src="*"></a>
    try:
        img = doc.xpath("//a[@class='cover-art']/img")[0]
        cover_url = img.attrib["src"]
    except IndexError:
        cover_url = ""
    return f"{track_count},{cover_url}"


def _get_corrected_stats_for_album(album_stats: Tuple) -> Dict:
    # fetch the number of tracks on that album
    # calculate the number of album plays
    # return as a list
    album_name, artist_name, scrobble_count, original_position = album_stats
    track_count, cover_url = _get_album_details(artist_name, album_name).split(",")
    album_scrobble_count = int(scrobble_count.replace(",", "")) / int(track_count)
    return dict(
        album_name=album_name,
        artist_name=artist_name,
        scrobble_count=scrobble_count,
        track_count=track_count,
        album_scrobble_count=album_scrobble_count,
        original_position=int(original_position),
        cover_url=cover_url,
    )


def correct_album_stats(stats: Iterable) -> Iterable[Dict]:
    return (_get_corrected_stats_for_album(stat) for stat in stats)


def correct_overview_stats(stats: Dict) -> Dict[int, Iterable[Dict]]:
    return {per: correct_album_stats(stats) for per, stats in stats.items()}


@lru_cache()
def username_exists(username):
    resp = session.head(f"https://www.last.fm/user/{username}")
    return resp.status_code == 200


@file_cache_decorator()
def get_username_start_year(username: str) -> str:
    print(f"Get username start year: {username}")
    page = session.get(f"https://www.last.fm/user/{username}", timeout=TIMEOUT).text
    m = re.search(r"scrobbling since \d{1,2} \w+ (\d{4})", page)
    return m.group(1)


@file_cache_decorator()
def get_image_base64(url: str) -> str:
    if not url:
        return ""
    print(url)
    data = session.get(url, timeout=TIMEOUT).content
    return base64.b64encode(data).decode("utf-8")


def get_album_stats_year_month(username, year, month=None):
    start_date = datetime(year=year, month=month or 1, day=1)
    if month:
        end_date = start_date + relativedelta(months=1)
    else:
        end_date = start_date + relativedelta(years=1)
    url = f"https://www.last.fm/user/{username}/library/albums?from={start_date.strftime('%Y-%m-%d')}&to={end_date.strftime('%Y-%m-%d')}"
    return get_album_stats(username, url)


def get_overview_per_year(username: str) -> Dict[int, Iterable]:
    overview = dict()
    start_year = int(get_username_start_year(username))
    today = datetime.today()
    current_year = today.year
    for year in range(start_year, current_year):
        stats = get_album_stats_year_month(username, year)
        overview[year] = stats if len(stats) else []
    return overview


def get_overview_per_month(username: str, year: int) -> Dict[int, Iterable]:
    today = datetime.today()
    assert year < today.year, "Year should be in the past"
    start_year = int(get_username_start_year(username))
    assert year >= start_year, f"Account was created in {start_year}"
    overview = dict()
    for month in range(1, 12 + 1):
        stats = get_album_stats_year_month(username, year, month)
        overview[month] = stats if len(stats) else []
    return overview


def get_album_stats_inc_random(username, drange, overview_per=None):
    if drange == "random":
        url = None
        stats = []
        tries = 0
        while not len(stats) and tries < 10:
            blast_name, period, url = get_random_interval_from_library(username)
            # need to test if the user has listening data in the selected interval
            # special case, use url as 'drange'
            stats = get_album_stats(username, url)
            tries += 1
        return stats, blast_name, period
    elif drange == "overview":
        if overview_per:
            year = int(overview_per)
            return get_overview_per_month(username, year), drange, drange
        return get_overview_per_year(username), drange, drange
    return get_album_stats(username, drange), drange, drange


if __name__ == "__main__":
    from sys import argv

    if len(argv) < 2:
        raise Exception(
            'Give username as first argument. And optionally the range 7/30/90/180/365 as second argument. If you provide nothing, this implies an infinite range. If you provide "random", this implies a random period from your listening history. If you provide "overview", this implies an overview per year. Optional third argument is to drill down the overview'
        )
    overview_per = None
    if len(argv) < 3:
        drange = None
    else:
        drange = argv[2]
        assert drange in ["random", "overview"] or int(drange) in (7, 30, 90, 180, 365)
        if drange == "overview" and len(argv) == 4:
            overview_per = argv[3]
            assert len(overview_per) == 4, "Overview drilldown must be a year"
    username = argv[1]
    stats, blast_name, period = get_album_stats_inc_random(
        username, drange, overview_per
    )
    corrected = (
        correct_album_stats(stats)
        if drange != "overview"
        else correct_overview_stats(stats)
    )
    range_str = (
        "all time"
        if drange is None
        else f"the last {drange} days"
        if drange not in ["random", "overview"]
        else f"{blast_name} ({period}) (blast from the past)"
        if drange == "random"
        else "overview per year"
    )
    print(f"Album stats for {username} for {range_str}:")
    print()
    ARTIST_LEN = 30
    ALBUM_LEN = 40
    if drange == "overview":
        print(
            f"{overview_per or 'Year':>4} {'Album':<{ALBUM_LEN}} {'Artist':<{ARTIST_LEN}}"
        )
        for per, corr in corrected.items():
            corr_list = list(corr)
            if not corr_list:
                print(f"{per:>4}")
            else:
                top_album = sorted(corr_list, key=lambda x: -x["album_scrobble_count"])[
                    0
                ]
                print(
                    f"{per:>4} {top_album['album_name']:<{ALBUM_LEN}} {top_album['artist_name']:<{ARTIST_LEN}}"
                )
    else:
        print(f"   {'Album':<{ALBUM_LEN}} {'Artist':<{ARTIST_LEN}}")
        for i, s in enumerate(
            sorted(list(corrected), key=lambda x: -x["album_scrobble_count"]), start=1
        ):
            print(
                f"{i:>2} {s['album_name']:<{ALBUM_LEN}} {s['artist_name']:<{ARTIST_LEN}}"
            )
