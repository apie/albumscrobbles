import unittest
import re

from freezegun import freeze_time

from scrape import username_regex
from subscribe_util import get_most_recent_period


class TestUserName(unittest.TestCase):
    def test_username_regex(self):
        username_list = [
            ("a1", True),
            ("a1234567890", True),
            ("a1234567890-_", True),
            ("a12345678912345", True),
            ("a", False),
            ("a()", False),
            ("aa ", False),
            ("123", False),
            ("a123456789123456", False),
        ]
        for username, valid in username_list:
            with self.subTest(username=username):
                self.assertEqual(re.match(username_regex, username) is not None, valid)


class TestMostRecentWeeknumber(unittest.TestCase):
    @freeze_time('2024-12-24')
    def test_weeknumber_51(self):
        period = get_most_recent_period("week")
        year, week = period['year'], period['week']
        assert year == 2024, year
        assert week == 51, week

    @freeze_time('2024-12-31')
    def test_weeknumber_52(self):
        period = get_most_recent_period("week")
        year, week = period['year'], period['week']
        assert year == 2024, year
        assert week == 52, week

    @freeze_time('2025-01-07')
    def test_weeknumber_1(self):
        period = get_most_recent_period("week")
        year, week = period['year'], period['week']
        assert year == 2025, year
        assert week == 1, week

    @freeze_time('2025-01-14')
    def test_weeknumber_2(self):
        period = get_most_recent_period("week")
        year, week = period['year'], period['week']
        assert year == 2025, year
        assert week == 2, week


if __name__ == "__main__":
    unittest.main()
