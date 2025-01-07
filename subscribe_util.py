import smtplib
import datetime
from functools import lru_cache
from dateutil.relativedelta import relativedelta
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.exc import BadSignature

from typing import Dict

from util import get_period_stats
from config import SECRET_KEY, FROM_ADDRESS

CONFIRMATION_SALT = 'confirmation'
EMAIL_TYPES = ('weekly', 'monthly', 'yearly')


def generate_confirmation_token(email):
    # https://realpython.com/handling-email-confirmation-in-flask/
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    return serializer.dumps(email, salt=CONFIRMATION_SALT)


def confirm_token(token, expiration=3600):
    # https://realpython.com/handling-email-confirmation-in-flask/
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    try:
        return serializer.loads(
            token,
            salt=CONFIRMATION_SALT,
            max_age=expiration
        )
    except BadSignature:
        raise ValueError('Invalid or expired token')


def send_confirmation_email(username, email, debug):
    token = generate_confirmation_token((username, email))
    subject = 'Confirm your subscription to albumscrobbles.com'
    host = 'https://www.albumscrobbles.com' if not debug else 'http://localhost:5000'
    confirmation_link = f'{ host }/subscribe_confirm?token={ token }'
    body = f"""
Hello,
You signed up to https://www.albumscrobbles.com using the username { username } and the e-mail address { email }.
Confirm your subscription by clicking the following link:

  { confirmation_link }

If you did not request this subscription, you can just ignore this e-mail.

Regards,
Denick from albumscrobbles.com
    """

    if debug:
        print(body)
        return
    # Connect to a local mailserver with a smarthost.
    with smtplib.SMTP('localhost') as conn:
        msg = EmailMessage()
        msg['From'] = FROM_ADDRESS
        msg['To'] = email
        msg['Subject'] = subject
        msg.set_content(body)
        conn.send_message(msg)


def save_confirmed_subscription(username, email):
    # Check existing subscriptions
    with open("confirmed_subscriptions.txt", "r") as f:
        subscriber_lines = f.readlines()
    subscription_details = "\t".join((username, email))
    if subscription_details not in map(str.strip, subscriber_lines):
        # Add to list of subscribers
        with open("confirmed_subscriptions.txt", "a") as f:
            f.write(subscription_details + "\n")
        print('Added subscription', subscription_details)


def get_most_recent_period(period_name: str) -> Dict[str, int]:
    today = datetime.date.today()
    if period_name == 'year':
        return dict(year=today.year - 1)
    if period_name == 'month':
        d = today - relativedelta(months=1)
        return dict(year=d.year, month=d.month)
    if period_name == 'week':
        today_last_week = today - relativedelta(weeks=1)
        return dict(year=int(today_last_week.strftime("%G")), week=int(today_last_week.strftime("%V")))
    raise NotImplementedError(f'Unknown {period_name=}')


def get_period_str(period_dict):
    if week := period_dict.get('week'):
        return f"week { week }"
    if month := period_dict.get('month'):
        from app import monthname
        return monthname(month)
    return period_dict.get('year')


def get_permalink(username, period_dict, debug):
    base_url = 'https://www.albumscrobbles.com' if not debug else 'http://localhost:5000'
    year = period_dict.get('year')
    if week := period_dict.get('week'):
        return base_url + f'/get_stat?username={ username }&year={ year }&week={ week }'
    if month := period_dict.get('month'):
        return base_url + f'/get_stat?username={ username }&year={ year }&month={ month }'
    return base_url + f'/get_stat?username={ username }&year={ year }'


def get_stat_for(username, email_type, period, debug):
    assert email_type in EMAIL_TYPES
    period_name = email_type.rstrip('ly')
    stats = get_period_stats(username, period.get('year'), period.get('month'), period.get('week'))
    top_album_str = nothing = None
    if not stats:
        nothing = f'You didnt listen to any music last { period_name }!'
    else:
        top_album = stats[0]
        top_album_str = f"""
    Your top album last { period_name } was
        { top_album['album_name'] } by { top_album['artist_name'] }
    """
    subject = f'{ username.capitalize() }, here are your real album stats for { get_period_str(period) }'
    permalink = get_permalink(username, period, debug)
    lastfm_link = f'https://www.last.fm/user/{ username }/listening-report/{ period_name }'
    body = f"""{ nothing or top_album_str}

For more information go to
- { permalink }
- or { lastfm_link }
    """
    return subject, permalink, lastfm_link, body


def get_stat_for_email(username, email_type, debug):
    period_name = email_type.rstrip('ly')
    period = get_most_recent_period(period_name)
    subject, permalink, lastfm_link, body = get_stat_for(username, email_type, period, debug)
    body = f"""
{subject}.

{ body }

To unsubscribe from these emails, send me an email: d@d87.nl

Regards,
Denick from albumscrobbles.com
    """
    return subject, body


@lru_cache()
def get_stat_for_rss(username, email_type, year, month=None, week=None, debug=False):
    period = dict(year=year, month=month, week=week)
    subject, permalink, lastfm_link, body = get_stat_for(username, email_type, period, debug)
    body = body.replace('\n', '<br>').replace(permalink, f'<a href="{permalink}">{permalink}</a>').replace(lastfm_link, f'<a href="{lastfm_link}">{lastfm_link}</a>')
    return subject, permalink, body


def send_periodic_emails(subscriber_lines, email_type, debug):
    # Connect to a local mailserver with a smarthost.
    with smtplib.SMTP('localhost') as conn:
        for subscriber_line in subscriber_lines:
            username, email = subscriber_line
            subject, body = get_stat_for_email(username, email_type, debug)
            if debug:
                print('-' * 80)
                print(body)
                continue
            msg = EmailMessage()
            msg['From'] = FROM_ADDRESS
            msg['To'] = email
            msg['Subject'] = subject
            msg.set_content(body)
            conn.send_message(msg)


def get_feed_items(username):
    from app import app
    debug = app.config['DEBUG']
    today = datetime.date.today()
    for dn in range(30, 0, -1):
        d = today - datetime.timedelta(days=dn)
        yesterday = d - datetime.timedelta(days=1)
        if d.month == 1 and d.day == 1:
            title, link, description = get_stat_for_rss(
                username,
                'yearly',
                year=yesterday.year,
                debug=debug,
            )
            yield dict(
                title=title,
                link=link,
                description=description,
                date=d,
            )
        if d.day == 1:
            title, link, description = get_stat_for_rss(
                username,
                'monthly',
                year=yesterday.year,
                month=yesterday.month,
                debug=debug,
            )
            yield dict(
                title=title,
                link=link,
                description=description,
                date=d,
            )
        if d.weekday() == 0:  # Monday
            year = yesterday.year
            week = int(yesterday.strftime("%V"))
            if week >= 52 and yesterday.year == today.year:
                year = year - 1
            title, link, description = get_stat_for_rss(
                username,
                'weekly',
                year=year,
                week=week,
                debug=debug,
            )
            yield dict(
                title=title,
                link=link,
                description=description,
                date=d,
            )
