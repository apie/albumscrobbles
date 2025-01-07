import unittest
import re

from scrape import username_regex


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


if __name__ == '__main__':
    unittest.main()
