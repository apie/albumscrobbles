#!/usr/bin/env python
# By Apie
# 2020-12-06


from flask import Flask, request
from jinja2 import Environment, PackageLoader, select_autoescape
from functools import lru_cache

import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

app = Flask(__name__)
env = Environment(
    loader=PackageLoader('app', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

from scrape import get_album_stats, correct_album_stats, username_exists

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.route("/")
@lru_cache()
def index():
    return env.get_template('index.html').render(
        title='Welcome!'
    )

def get_user_stats(username, drange=None):
    assert username and username_exists(username)
    print(f"Get {username} {drange}")
    stats = get_album_stats(username, drange)
    corrected = correct_album_stats(stats)
    sorted_list = sorted(list(corrected), key=lambda x: -x['album_scrobble_count'])
    return env.get_template('stats.html').render(
        title=f'Album stats for {username}',
        username=username,
        stats=sorted_list,
        range=drange,
    )

@app.route("/get_stats")
def get_stats():
    username = request.args.get('username')
    drange = request.args.get('range')
    try:
        return get_user_stats(username, drange)
    except AssertionError as e:
        print(e)
        return f'Invalid user {username}', 404

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
