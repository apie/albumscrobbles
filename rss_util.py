import xml.etree.ElementTree
from min_rss_gen.generator import start_rss, gen_item

from subscribe_util import get_feed_items


def generate_feed(username):
    rss_items = [
        gen_item(
            title=item['title'],
            link=item['link'],
            description=item['description'],
            pubDate=item['date'].isoformat(),
        )
        for item in get_feed_items(username)
    ]

    rss_xml_element = start_rss(
        title=f"Albumscrobbles feed for { username }",
        link=f"www.albumscrobbles.com/feed/{ username }",
        description="Your real album stats per week, month and year.",
        items=rss_items,
    )

    return xml.etree.ElementTree.tostring(rss_xml_element)
