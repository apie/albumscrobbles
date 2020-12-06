#!/usr/bin/env python
# By Apie
# 2020-12-06

# TODO
# Async celery uvicorn? Start off with sync gunicorn and 2 workers
# Favicon
# Show some recent users and top albums on the front page?
# Create dockerfile and deploy to openode.io (NOTE: there we can not use the file cache)
# Write blogpost
# User-sortable columns
# Hyperlinks to last.fm album/artist pages
# Album images

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


@app.route("/")
@lru_cache()
def index():
    return env.get_template('index.html').render(
        title='Welcome!'
    )

@lru_cache()
def get_user_stats(username):
    if not username or not username_exists(username):
        return f'Invalid user {username}' # TODO status code
    print(f"Get {username}")
    stats = get_album_stats(username)
    corrected = correct_album_stats(stats)
    # Sort by album plays
    sorted_list = sorted(list(corrected), key=lambda x: -x[4])
    return env.get_template('stats.html').render(
        title=f'Album stats for {username}',
        username=username,
        stats=sorted_list,
    )

@app.route("/get_stats")
def get_stats():
    return get_user_stats(request.args.get('username'))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000)
