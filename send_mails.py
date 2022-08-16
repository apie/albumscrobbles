#!/usr/bin/env python
import click

from subscribe_util import send_periodic_emails, EMAIL_TYPES


@click.command("send-emails")
@click.argument("email_type", type=click.Choice(EMAIL_TYPES))
@click.argument("debug", type=bool, default=False)
def send_emails(email_type, debug):
    """Sends the periodic emails to the subscribers"""

    with open("confirmed_subscriptions.txt", "r") as f:
        subscriber_lines = f.readlines()
        send_periodic_emails((
            subscriber.strip().split("\t")
            for subscriber in subscriber_lines
        ), email_type, debug)

    print('Done.')

if __name__ == '__main__':
    send_emails()