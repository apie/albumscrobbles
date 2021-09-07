#!/usr/bin/env python
# By Apie
# 2020-12-06


from flask import Flask, request, send_file
from jinja2 import Environment, PackageLoader, select_autoescape

import sys
import urllib.parse
from os import path, truncate

from datetime import datetime
from functools import wraps
from typing import List


RECENT_USERS_FILE = 'recent.txt'


def logger():
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"[{datetime.now()}] Call {func.__name__}({', '.join(arg for arg in args if arg)})")
            return func(*args, **kwargs)
        return wrapper
    return inner


sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
app = Flask(__name__)
env = Environment(
    loader=PackageLoader('app', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

from flask_apscheduler import APScheduler

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


from scrape import get_album_stats_inc_random, correct_album_stats, username_exists, cache_binary_url_and_return_path
from file_cache import file_cache_decorator


@file_cache_decorator(keep_days=1)
def get_recent_users():
    # Use a file cache because we use multiple workers
    try:
        with open(RECENT_USERS_FILE) as f:
            return f.read()
    except FileNotFoundError:
        return ''

def add_recent_user(username):
    with open(RECENT_USERS_FILE, 'a') as f:
        f.write(username+'\n')

def trunc_recent_user_file(latest_recent_users: List):
    # most recent user is at the start of the list, so we reverse the list to put the most recent user at the end of the file
    truncate(RECENT_USERS_FILE, 0)
    for u in reversed(latest_recent_users):
        add_recent_user(u)

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route('/static/cover/<path:file_name>')
def static_cover(file_name):
    if file_name == 'unknown.png':
        return app.send_static_file(file_name)
    # Undo the replace and get the file path from the cache. We use the real file path here so send_file() can use it to set the appropriate last-modified headers.
    return send_file(cache_binary_url_and_return_path(file_name.replace('-', '/')))

def get_user_top_albums(username):
    corrected_sorted, original_album, original_artist, top_album_cover_filename, _, _ = get_user_stats(username, None)
    return corrected_sorted[0] if corrected_sorted else None

import json

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
def index():
    return env.get_template('index.html').render(
        title='Welcome!',
        recent_users=json.loads(get_recent_users_with_stats())
    )

from jobssynchronizer import JobsSynchronizer
from scrape import _get_corrected_stats_for_album

def _get_corrected_stats_for_album_thread(job_synchronizer, task_id, stat):
    result = _get_corrected_stats_for_album(stat)
    job_synchronizer.notify_task_completion(result)

def correct_album_stats_thread(stats):
    if not stats:
        return ()
    job_synchronizer = JobsSynchronizer(len(stats))
    for i, stat in enumerate(stats):
        app.apscheduler.add_job(func=_get_corrected_stats_for_album_thread, trigger='date', args=[job_synchronizer, i, stat], id='j' + str(i), max_instances=10, misfire_grace_time=60)
    job_synchronizer.wait_for_tasks_to_be_completed()
    return job_synchronizer.get_status_list()

def get_user_stats(username: str, drange: str):
    username = username.strip()
    assert username and username_exists(username)
    stats, blast_name, period = get_album_stats_inc_random(username, drange)
    # Sort by total plays
    sorted_stats = sorted(stats, key=lambda x: -int(x[2].replace(',', '')))
    #  and get the first, to get original top album.
    original_album, original_artist, _orginal_playcount, _original_position = sorted_stats[0] if sorted_stats else (None,None,None,None)
    corrected = correct_album_stats_thread(stats)
    corrected_sorted = sorted(list(corrected), key=lambda x: -x['album_scrobble_count'])
    top_album_cover_filename = 'unknown.png'
    if corrected_sorted and corrected_sorted[0] and corrected_sorted[0]['cover_url']:
        # Replace part of the url to be able to pass it as a file name.
        top_album_cover_filename = corrected_sorted[0]['cover_url'].replace('/','-')
    return corrected_sorted, original_album, original_artist, top_album_cover_filename, blast_name, period

@logger()
def render_user_stats(username: str, drange: str):
    username = username.strip()
    assert username and username_exists(username)
    add_recent_user(username)
    corrected_sorted, original_album, original_artist, top_album_cover_filename, blast_name, blast_period = get_user_stats(username, drange)
    return env.get_template('stats.html').render(
        title=f'Album stats for {username} ({drange+" days" if drange else "all time"})',
        username=username,
        original_top_album=dict(
            name=original_album,
            artist=original_artist,
        ),
        stats=corrected_sorted,
        top_album_cover_path='/static/cover/'+top_album_cover_filename,
        ranges=(7,30,90,180,365,'','random'),
        selected_range=drange,
        blast_name=blast_name,
        blast_period=blast_period,
    )

@app.route("/get_stats")
def get_stats():
    username = request.args.get('username')
    if username:
        username = username.replace('https://www.last.fm/user/', '') # allow to enter user url as username
    if not username:
        return 'Username required', 400
    drange = request.args.get('range')
    try:
        return render_user_stats(username, drange)
    except AssertionError as e:
        print(e)
        return f'Invalid user {username}', 404

@app.route("/correction")
def correction():
    artist, album, count = request.args.get('artist'), request.args.get('album'), request.args.get('count')
    if not artist or not album or not count:
        return 'Artist, album and count required', 400
    return env.get_template('correction.html').render(title='Enter your suggestion', artist=artist, album=album, original_count=count)

@app.route("/correction_post", methods=['POST'])
def correction_post():
    artist, album, original_count, count = request.form['artist'], request.form['album'], request.form['original_count'], request.form['count']
    artist = urllib.parse.unquote_plus(artist)
    album = urllib.parse.unquote_plus(album)
    correction = '\t'.join((artist, album, original_count, count))
    with open('corrections.txt', 'a') as f:
        f.write(correction+'\n')
    return env.from_string('''
{% extends "base.html" %}
{% block content %}
{{text}}
{% endblock %}
        ''').render(title='Thank you for your suggestion', text='OK, thank you. Your correction will be considered.')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
