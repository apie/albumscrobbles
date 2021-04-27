#!/usr/bin/env python
# By Apie
# 2020-12-06


from flask import Flask, request, send_file
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


from scrape import get_album_stats, correct_album_stats, username_exists, cache_binary_url_and_return_path
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

@app.route('/static/cover/<path:file_name>')
def static_cover(file_name):
    if file_name == 'unknown.png':
        return app.send_static_file(file_name)
    # Undo the replace and get the file path from the cache. We use the real file path here so send_file() can use it to set the appropriate last-modified headers.
    return send_file(cache_binary_url_and_return_path(file_name.replace('-', '/')))

@app.route("/")
@logger()
def index():
    return env.get_template('index.html').render(
        title='Welcome!',
        recent_users=get_recent_users().splitlines(),
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

def get_user_stats(username, drange=None):
    username = username.strip()
    assert username and username_exists(username)
    add_recent_user(username)
    stats = get_album_stats(username, drange)
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
    return corrected_sorted, original_album, original_artist, top_album_cover_filename

@logger()
def render_user_stats(username, drange=None):
    corrected_sorted, original_album, original_artist, top_album_cover_filename = get_user_stats(username, drange)
    return env.get_template('stats.html').render(
        title=f'Album stats for {username} ({drange+" days" if drange else "all time"})',
        username=username,
        original_top_album=dict(
            name=original_album,
            artist=original_artist,
        ),
        stats=corrected_sorted,
        top_album_cover_path='/static/cover/'+top_album_cover_filename,
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
