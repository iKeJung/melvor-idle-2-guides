import unittest

from money_making import compare


class MoneyMakingTests(unittest.TestCase):
    def test_personal_comparison_requires_readable_bank_inventory(self):
        cases = {
            "absent": {"components_present": {}, "warnings": []},
            "unreadable": {
                "components_present": {"Bank": ["Inventory"]},
                "warnings": ["could not decode Bank/Inventory: truncated component"],
            },
        }
        for label, decoded in cases.items():
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "The bank could not be decoded"):
                    compare({"Objects": {"Item": []}}, snapshot={}, decoded=decoded)


if __name__ == "__main__":
    unittest.main()
