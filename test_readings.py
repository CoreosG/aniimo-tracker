import unittest
from readings import parse_amount, single_amount


class ReadingTests(unittest.TestCase):
    def test_ranking_change_keeps_sign_and_ignores_lifetime_total(self):
        from readings import rank_points_reading
        self.assertEqual(rank_points_reading('Imperador dos Ovos\n52530/52710\n+370\nPontos de ranque x2'),370)
        self.assertEqual(rank_points_reading('Egg Emperor\n52530/52710\n−140'),-140)
        self.assertIsNone(rank_points_reading('Imperador dos Ovos\n52530/52710\n370'))
        self.assertIsNone(rank_points_reading('Imperador dos Ovos\n52530/52710\n+370\n-140'))
        self.assertIsNone(rank_points_reading('Match loot\n+370'))

    def test_loot_label_selects_value_without_confusing_defeats_or_timer(self):
        from readings import loot_reading
        text='120 aps\nAventura\nSaque da partida\n420908\nTotal de derrotas\n14\n013:16\nBaús obtidos hoje: 6/6'
        self.assertEqual(loot_reading(text),420908)
        self.assertEqual(loot_reading('Match loot: 431719\nTotal defeats 14'),431719)
        self.assertIsNone(loot_reading('Saque da partida\nTotal de derrotas\n14'))
        self.assertIsNone(loot_reading('Saque da partida\n420908\nSaque da partida\n999'))
        self.assertIsNone(loot_reading('Total de derrotas 14',allow_unlabelled=True))
        self.assertEqual(loot_reading('431719',allow_unlabelled=True),431719)

    def test_signed_point_losses_are_preserved_without_allowing_negative_currency(self):
        from readings import parse_points, single_points
        self.assertEqual(parse_points('-140'), -140)
        self.assertEqual(parse_points('− 140'), -140)
        self.assertEqual(single_points('−140'), -140)
        self.assertEqual(single_points('+192'), 192)
        self.assertIsNone(single_points('47723 / 47850'))
        self.assertIsNone(single_amount('-140'))
        with self.assertRaises(ValueError): parse_amount('-140')
        with self.assertRaises(ValueError): parse_points('--140')

    def test_inventory_ocr_decimal_zero_preserves_currency_multiplier(self):
        # Windows OCR's actual reading from the 7,654,000 inventory capture.
        self.assertEqual(single_amount('7654.O K'),7654000)

    def test_malformed_amount_is_not_truncated_to_a_smaller_integer(self):
        for text in ('7654.X K','7654.O','7654.','7654.0 X','7654.K'):
            with self.subTest(text=text):self.assertIsNone(single_amount(text))

    def test_inventory_abbreviation_and_point_award(self):
        self.assertEqual(parse_amount('9637.5 K'), 9637500)
        self.assertEqual(parse_amount('9637,5 K'), 9637500)
        self.assertEqual(parse_amount('9.6 M'), 9600000)
        self.assertEqual(single_amount('+192'), 192)
        self.assertEqual(single_amount('431719'), 431719)

    def test_uncertain_or_multiple_numbers_are_never_glued_together(self):
        self.assertIsNone(single_amount('47723/47850'))
        self.assertIsNone(single_amount('9637.5'))
        self.assertEqual(parse_amount('9,637,500'), 9637500)
        self.assertEqual(parse_amount('9.637.500'), 9637500)


if __name__ == '__main__':
    unittest.main()
