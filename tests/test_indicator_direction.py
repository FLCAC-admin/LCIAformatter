import unittest

from lciafmt.jsonld import indicator_direction


class IndicatorDirectionTest(unittest.TestCase):

    def test_emissions_are_output(self):
        self.assertEqual(
            indicator_direction(['emission/air', 'emission/water']),
            'OUTPUT')

    def test_resources_are_input(self):
        self.assertEqual(
            indicator_direction(['resource/ground', 'resource/air']),
            'INPUT')

    def test_mixed_is_unspecified(self):
        self.assertIsNone(indicator_direction([
            'emission/air',
            'resource/ground',
        ]))

    def test_empty_is_unspecified(self):
        self.assertIsNone(indicator_direction([]))


if __name__ == "__main__":
    unittest.main()
