#!/usr/bin/env python
# By Apie
# 2020-12-06


import json
from flask import Flask, request, send_file, make_response
from jinja2 import Environment, PackageLoader, select_autoescape
from flask_apscheduler import APScheduler


import sys
from os import path, getenv

from datetime import datetime
from functools import lru_cache
from calendar import month_name

from scrape import (
    username_exists,
    cache_binary_url_and_return_path,
)
from util import (
    render_title_template,
    render_msg_template,
    logger,
    get_recent_users_with_stats,
    add_recent_user,
    get_user_stats,
    get_user_overview,
    render_overview_block,
    save_correction,
    get_period_stats,
)
from subscribe_util import (
    send_confirmation_email,
    confirm_token,
    save_confirmed_subscription,
)
from rss_util import generate_feed


sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
app = Flask(__name__)

env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


# ############# routes #######################


@app.route("/")
@logger()
@lru_cache()
def index():
    return env.get_template("index.html").render(
        title="Welcome!", recent_users=json.loads(get_recent_users_with_stats())
    )


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")


@app.route("/static/cover/<path:file_name>")
def static_cover(file_name):
    if file_name == "unknown.png":
        return app.send_static_file(file_name)
    # Undo the replace and get the file path from the cache. We use the real file path here so send_file() can use it to set the appropriate last-modified headers.
    return send_file(cache_binary_url_and_return_path(file_name.replace("-", "/")))


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


@app.route("/get_stat")
def period_stats():
    username = request.args.get("username")
    year = request.args.get("year")
    year = int(year) if year else None
    month = request.args.get("month")
    month = int(month) if month else None
    week = request.args.get("week")
    week = int(week) if week else None
    if week:
        period_str = f'week { week } of { year }'
    elif month:
        period_str = f'{ monthname(month) } of { year }'
    else:
        period_str = year
    corrected_sorted = get_period_stats(username, year, month, week)
    top_album_cover_filename = "unknown.png"
    if corrected_sorted and corrected_sorted[0] and corrected_sorted[0]["cover_url"]:
        # Replace part of the url to be able to pass it as a file name.
        top_album_cover_filename = corrected_sorted[0]["cover_url"].replace("/", "-")
    return env.get_template("simple_stats.html").render(
        title=f'Album stats for {username}',
        username=username,
        period_str=period_str,
        stats=corrected_sorted,
        top_album_cover_path="/static/cover/" + top_album_cover_filename,
        disable_menu=True,
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
                return render_title_template(
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
        return render_title_template(
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
    save_correction(artist, album, original_count, count)
    return render_msg_template(
        title="Thank you for your suggestion",
        text="OK, thank you. Your correction will be considered.",
    )


@app.route("/subscribe")
def subscribe():
    username = request.args.get("username")
    if not username:
        return "username required", 400
    return env.get_template("subscribe.html").render(
        title="Subscribe by e-mail",
        username=username
    )


@app.route("/subscribe_post", methods=["POST"])
def subscribe_post():
    username, email, robot = (
        request.form["username"],
        request.form["email"],
        request.form.get("robot"),
    )
    if robot:
        return 'Are you a robot? Only humans allowed.', 400
    send_confirmation_email(username, email, app.config['DEBUG'])
    return render_msg_template(
        title="Thank you for your subscription",
        text="Thank you for subscribing. Please check your inbox, we sent a confirmation e-mail.",
    )


@app.route("/subscribe_confirm")
def subscribe_confirm():
    token = request.args.get("token")
    if not token:
        return "token required", 400
    try:
        username, email = confirm_token(token)
    except ValueError as e:
        return str(e), 400
    save_confirmed_subscription(username, email)
    return render_msg_template(
        title="Thank you for confirming your subscription",
        text=f"Thank you for confirming your subscription { username }! You should start receiving e-mails soon.",
    )


@app.route("/feed/<path:username>")
def feed(username):
    username = username.strip()
    if not username_exists(username):
        return 'Unknown user', 404
    rss_xml = generate_feed(username)
    response = make_response(rss_xml)
    response.headers['Content-Type'] = 'text/xml'
    return response

# ############# /routes #######################


# Define custom jinja filters and globals
def monthname(month_num):
    return month_name[month_num]


env.filters["monthname"] = monthname
env.globals["enable_goatcounter"] = bool(getenv("GOATCOUNTER"))
env.globals["enable_blastfromthepast"] = bool(getenv("BLASTFROMTHEPAST"))
env.globals["enable_overview"] = bool(getenv("OVERVIEW"))
env.globals["enable_subscription"] = bool(getenv("SUBSCRIPTION"))
##############################


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
