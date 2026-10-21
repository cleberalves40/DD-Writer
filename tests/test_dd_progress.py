import unittest

from dd_writer import parse_dd_transferred_bytes


class DdProgressParsingTests(unittest.TestCase):
    def test_parses_freebsd_progress_with_parenthesized_units(self):
        line = " 10485760 bytes (10 MB, 10 MiB) transferred 1.038s, 10 MB/s"
        self.assertEqual(parse_dd_transferred_bytes(line), 10485760)

    def test_parses_progress_without_parenthesized_units(self):
        self.assertEqual(parse_dd_transferred_bytes("123 bytes transferred"), 123)

    def test_ignores_non_progress_lines(self):
        self.assertIsNone(
            parse_dd_transferred_bytes("dd: /dev/da0: Permission denied")
        )


if __name__ == "__main__":
    unittest.main()