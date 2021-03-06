#!/usr/bin/env python
# By Apie
# 2020-12-06


import json
from flask import Flask, request, send_file
from jinja2 import Environment, PackageLoader, select_autoescape
from flask_apscheduler import APScheduler

import sys
import urllib.parse
from os import path, truncate, getenv

from datetime import datetime
from functools import wraps, lru_cache
from typing import List
from calendar import month_name

from scrape import (
    get_album_stats_inc_random,
    _get_corrected_stats_for_album,
    username_exists,
    cache_binary_url_and_return_path,
    get_album_stats_year_month,
    get_album_stats_year_week,
    get_username_start_year,
)
from jobssynchronizer import JobsSynchronizer
from file_cache import file_cache_decorator

RECENT_USERS_FILE = "recent.txt"


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


sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
app = Flask(__name__)
env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


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


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")


@app.route("/static/cover/<path:file_name>")
def static_cover(file_name):
    if file_name == "unknown.png":
        return app.send_static_file(file_name)
    # Undo the replace and get the file path from the cache. We use the real file path here so send_file() can use it to set the appropriate last-modified headers.
    return send_file(cache_binary_url_and_return_path(file_name.replace("-", "/")))


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


@app.route("/")
@logger()
@lru_cache()
def index():
    return env.get_template("index.html").render(
        title="Welcome!", recent_users=json.loads(get_recent_users_with_stats())
    )


def _get_corrected_stats_for_album_thread(job_synchronizer, task_id, stat):
    result = _get_corrected_stats_for_album(stat)
    job_synchronizer.notify_task_completion(result)


def correct_album_stats_thread(stats):
    if not stats:
        return ()
    job_synchronizer = JobsSynchronizer(len(stats))
    for i, stat in enumerate(stats):
        app.apscheduler.add_job(
            func=_get_corrected_stats_for_album_thread,
            trigger="date",
            args=[job_synchronizer, i, stat],
            id="j" + str(i),
            max_instances=10,
            misfire_grace_time=60,
        )
    job_synchronizer.wait_for_tasks_to_be_completed()
    return job_synchronizer.get_status_list()


@app.route("/get_stats/detail")
def render_album_stats_year_month():
    username = request.args.get("username")
    year = request.args.get("year")
    year = None if year == 'None' else int(year)
    month = request.args.get("month")
    month = None if month in ['', 'None'] else int(month)
    week = request.args.get("week")
    week = None if week in ['', 'None'] else int(week)
    return render_overview_block(username, year, month, week)


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


@logger()
def render_user_stats(username: str, drange: str, year: str = None, overview_per_week: bool = False):
    username = username.strip()
    assert username and username_exists(username)
    add_recent_user(username)
    if drange == "overview":
        overview = get_user_overview(username, year and int(year), overview_per_week)
        # Trick to get the start_year and current_year. The function is cached so it's quick.
        start_year = get_user_overview(username)[0]["year"]
        current_year = get_user_overview(username)[-1]["year"] + 1
        t = f"overview {year}" if year else "overview"
        if year:  # Prevent caching incorrect data forever if smart guy changed the url.
            today = datetime.today()
            if int(year) > today.year:
                msg = "Year should not be in the future"
                return env.from_string(
                    """
            {% extends "base.html" %}
            {% block content %}
            <h4>{{text}}</h4>
            {% endblock %}
                    """
                ).render(
                    title=msg,
                    text=msg,
                ), 404
        return env.get_template("overview.html").render(
            title=f"Album stats for {username} ({t})",
            year=year and int(year),
            start_year=start_year,
            current_year=current_year,
            username=username,
            overview=overview,
            per=overview_per_week and "week" or "month",
            selected_range=drange,
        )
    (
        corrected_sorted,
        original_album,
        original_artist,
        top_album_cover_filename,
        blast_name,
        blast_period,
    ) = get_user_stats(username, drange)
    return env.get_template("stats.html").render(
        title=f'Album stats for {username} ({drange+" days" if drange else "all time"})',
        username=username,
        original_top_album=dict(
            name=original_album,
            artist=original_artist,
        ),
        stats=corrected_sorted,
        top_album_cover_path="/static/cover/" + top_album_cover_filename,
        selected_range=drange,
        blast_name=blast_name,
        blast_period=blast_period,
    )


@app.route("/get_stats")
def get_stats():
    username = request.args.get("username")
    if username:
        username = username.replace(
            "https://www.last.fm/user/", ""
        )  # allow to enter user url as username
    if not username:
        return "Username required", 400
    drange = request.args.get("range")
    # TODO move user check to here
    # TODO move overview check to here
    year = drange == "overview" and request.args.get("year")
    overview_per_week = bool(drange == "overview" and request.args.get("per") == "week")
    try:
        return render_user_stats(username, drange, year, overview_per_week)
    except AssertionError as e:
        print(e)
        return env.from_string(
            """
    {% extends "base.html" %}
    {% block content %}
    <h4>{{text}}</h4>
    {% endblock %}
            """
        ).render(
            title="Invalid user",
            text=f"Invalid user {username}"
        ), 404


@app.route("/correction")
def correction():
    artist, album, count = (
        request.args.get("artist"),
        request.args.get("album"),
        request.args.get("count"),
    )
    if not artist or not album or not count:
        return "Artist, album and count required", 400
    return env.get_template("correction.html").render(
        title="Enter your suggestion", artist=artist, album=album, original_count=count
    )


@app.route("/correction_post", methods=["POST"])
def correction_post():
    artist, album, original_count, count = (
        request.form["artist"],
        request.form["album"],
        request.form["original_count"],
        request.form["count"],
    )
    if original_count == count:
        return "New count should be different from existing count", 400
    artist = urllib.parse.unquote_plus(artist)
    album = urllib.parse.unquote_plus(album)
    correction = "\t".join((artist, album, original_count, count))
    with open("corrections.txt", "a") as f:
        f.write(correction + "\n")
    return env.from_string(
        """
{% extends "base.html" %}
{% block content %}
{{text}}
{% endblock %}
        """
    ).render(
        title="Thank you for your suggestion",
        text="OK, thank you. Your correction will be considered.",
    )


# Define custom jinja filters and globals
def monthname(month_num):
    return month_name[month_num]


env.filters["monthname"] = monthname
env.globals["enable_goatcounter"] = bool(getenv("GOATCOUNTER"))
##############################

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
