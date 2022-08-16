import json
import urllib.parse

from datetime import datetime
from os import truncate
from typing import List
from functools import wraps, lru_cache

from jobssynchronizer import JobsSynchronizer
from file_cache import file_cache_decorator
from scrape import (
    _get_corrected_stats_for_album,
    get_album_stats_inc_random,
    get_album_stats_year_month,
    get_album_stats_year_week,
    username_exists,
    cache_binary_url_and_return_path,
    get_username_start_year,
)

RECENT_USERS_FILE = "recent.txt"


def render_msg_template(title, text):
    from app import env
    return env.from_string(
        """
{% extends "base.html" %}
{% block content %}
{{text}}
{% endblock %}
        """
    ).render(title=title, text=text)


def render_title_template(title, text):
    from app import env
    return env.from_string(
        """
{% extends "base.html" %}
{% block content %}
<h4>{{text}}</h4>
{% endblock %}
        """
    ).render(title=title, text=text)


def logger():
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(
                f"[{datetime.now()}] Call {func.__name__}({', '.join(str(arg) for arg in args if arg)})"
            )
            return func(*args, **kwargs)

        return wrapper

    return inner


@file_cache_decorator(keep_days=1)
def get_recent_users():
    # Use a file cache because we use multiple workers
    try:
        with open(RECENT_USERS_FILE) as f:
            return f.read()
    except FileNotFoundError:
        return ""


def add_recent_user(username):
    with open(RECENT_USERS_FILE, "a") as f:
        f.write(username + "\n")


def trunc_recent_user_file(latest_recent_users: List):
    # most recent user is at the start of the list, so we reverse the list to put the most recent user at the end of the file
    truncate(RECENT_USERS_FILE, 0)
    for u in reversed(latest_recent_users):
        add_recent_user(u)


def get_user_top_albums(username):
    (
        corrected_sorted,
        original_album,
        original_artist,
        top_album_cover_filename,
        _,
        _,
    ) = get_user_stats(username, None)
    return corrected_sorted[0] if corrected_sorted else None


@file_cache_decorator(keep_days=1)
def get_recent_users_with_stats():
    # recent users are appended to file so the most recent one is at the end of the file. We reverse so that it is now at the start of the list.
    # get last 10 unique recent users (keep order)
    recent_users = []
    for u in reversed(get_recent_users().splitlines()):
        if u not in recent_users:
            recent_users.append(u)
        if len(recent_users) >= 10:
            trunc_recent_user_file(recent_users[:10])
            break
    # get stats and dump to json to be able to cache it as string
    return json.dumps(list((u, get_user_top_albums(u)) for u in recent_users))


def _get_corrected_stats_for_album_thread(job_synchronizer, task_id, stat):
    result = _get_corrected_stats_for_album(stat)
    job_synchronizer.notify_task_completion(result)


def correct_album_stats_thread(stats):
    if not stats:
        return ()
    job_synchronizer = JobsSynchronizer(len(stats))
    from app import scheduler
    for i, stat in enumerate(stats):
        scheduler.add_job(
            func=_get_corrected_stats_for_album_thread,
            trigger="date",
            args=[job_synchronizer, i, stat],
            id="j" + str(i),
            max_instances=10,
            misfire_grace_time=60,
        )
    job_synchronizer.wait_for_tasks_to_be_completed()
    return job_synchronizer.get_status_list()


@lru_cache()
def render_overview_block(username, year, month, week):
    per_month = False
    if week:
        per = week
        stats = get_album_stats_year_week(username, year, week)
    elif month:
        per = month
        stats = get_album_stats_year_month(username, year, month)
        per_month = True
    else:
        stats = get_album_stats_year_month(username, year, None)
        per = year
        year = None
    if not stats:
        return ''  # No listening data in this period
    corrected = correct_album_stats_thread(stats)
    if not corrected:
        return ''  # No listening data in this period
    top_album = sorted(corrected, key=lambda x: -x["album_scrobble_count"])[0]
    if top_album["cover_url"]:
        # Cache it already (not needed for unknown.png)
        cache_binary_url_and_return_path(top_album["cover_url"])
        # Use our image proxy
        cover_url = "static/cover/" + top_album["cover_url"].replace("/", "-")
    else:
        cover_url = "static/cover/unknown.png"

    stat = dict(
        per=per,
        album_name=top_album["album_name"],
        artist_name=top_album["artist_name"],
        cover_url=cover_url,
    )
    from app import env
    return env.get_template("partials/overview_block.html").render(
        username=username,
        year=year,
        stat=stat,
        per_month=per_month,
    )


@lru_cache
def get_user_overview(username: str, year: int = None, overview_per_week: bool = False):
    retval = []
    if not year:
        start_year = int(get_username_start_year(username))
        today = datetime.today()
        current_year = today.year
        for year in range(start_year, current_year):
            retval.append(dict(year=year))
    else:
        if overview_per_week:
            for week in range(1, 53 + 1):
                retval.append(dict(week=week, year=year))
        else:
            for month in range(1, 12 + 1):
                retval.append(dict(month=month, year=year))
    return retval


def get_user_stats(username: str, drange: str):
    username = username.strip()
    assert username and username_exists(username)
    stats, blast_name, period = get_album_stats_inc_random(username, drange)
    # Sort by total plays
    sorted_stats = sorted(stats, key=lambda x: -int(x[2].replace(",", "")))
    #  and get the first, to get original top album.
    original_album, original_artist, _orginal_playcount, _original_position = (
        sorted_stats[0] if sorted_stats else (None, None, None, None)
    )
    corrected = correct_album_stats_thread(stats)
    corrected_sorted = sorted(list(corrected), key=lambda x: -x["album_scrobble_count"])
    top_album_cover_filename = "unknown.png"
    if corrected_sorted and corrected_sorted[0] and corrected_sorted[0]["cover_url"]:
        # Replace part of the url to be able to pass it as a file name.
        top_album_cover_filename = corrected_sorted[0]["cover_url"].replace("/", "-")
    return (
        corrected_sorted,
        original_album,
        original_artist,
        top_album_cover_filename,
        blast_name,
        period,
    )


def save_correction(artist, album, original_count, count):
    artist = urllib.parse.unquote_plus(artist)
    album = urllib.parse.unquote_plus(album)
    correction = "\t".join((artist, album, original_count, count))
    with open("corrections.txt", "a") as f:
        f.write(correction + "\n")
