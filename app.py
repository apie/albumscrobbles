#!/usr/bin/env python
# By Apie
# 2020-12-06


from flask import Flask, request
from jinja2 import Environment, PackageLoader, select_autoescape
from functools import lru_cache

import sys
from os import path

from datetime import datetime
from functools import wraps


def logger():
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"[{datetime.now()}] Get {func.__name__}({', '.join(arg for arg in args if arg)})")
            return func(*args, **kwargs)
        return wrapper
    return inner


sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
app = Flask(__name__)
env = Environment(
    loader=PackageLoader('app', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

from scrape import get_album_stats, correct_album_stats, username_exists, get_image_base64
from file_cache import file_cache_decorator


@file_cache_decorator(keep_days=1)
def get_recent_users():
    try:
        with open('recent.txt') as f:
            return f.read()
    except FileNotFoundError:
        return ''

def add_recent_user(username):
    with open('recent.txt', 'a') as f:
        f.write(username+'\n')

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route("/")
@logger()
def index():
    return env.get_template('index.html').render(
        title='Welcome!',
        recent_users=get_recent_users().splitlines(),
    )

@logger()
def get_user_stats(username, drange=None):
    username = username.strip()
    assert username and username_exists(username)
    add_recent_user(username)
    stats = get_album_stats(username, drange)
    # Sort by total plays
    sorted_stats = sorted(stats, key=lambda x: -int(x[2].replace(',', '')))
    #  and get the first, to get original top album.
    original_album, original_artist, _orginal_playcount, _original_position = sorted_stats[0] if sorted_stats else (None,None,None,None)
    corrected = correct_album_stats(stats)
    corrected_sorted = sorted(list(corrected), key=lambda x: -x['album_scrobble_count'])
    top_album_cover_data = get_image_base64(corrected_sorted[0]['cover_url']) if corrected_sorted else ''
    return env.get_template('stats.html').render(
        title=f'Album stats for {username} ({drange+" days" if drange else "all time"})',
        username=username,
        original_top_album=dict(
            name=original_album,
            artist=original_artist,
        ),
        stats=corrected_sorted,
        top_album_cover_data=top_album_cover_data,
        ranges=(7,30,90,180,365,''),
        selected_range=drange,
    )

@app.route("/get_stats")
def get_stats():
    username = request.args.get('username')
    if not username:
        return 'Username required', 400
    drange = request.args.get('range')
    try:
        return get_user_stats(username, drange)
    except AssertionError as e:
        print(e)
        return f'Invalid user {username}', 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
