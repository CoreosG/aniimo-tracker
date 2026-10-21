import unittest
from screen_kind import screen_kind


class ScreenKindTests(unittest.TestCase):
    def test_recognizes_negative_point_result_labels(self):
        self.assertEqual(screen_kind('Imperador dos Ovos\n47583/47670\n-140'), 'points')
        self.assertEqual(screen_kind('Egg Emperor\n47583/47670\n−140'), 'points')

    def test_identifies_labels_from_actual_portuguese_screens(self):
        self.assertEqual(screen_kind('Inventário a 1/34 kg\nMochila de Aventura\nCofre\n9637.5 K'),'balance')
        self.assertEqual(screen_kind('Aventura\nSaque da partida\n431719\nTotal de derrotas'),'money')
        self.assertEqual(screen_kind('Imperador dos Ovos\n47723/47850\n+192'),'points')

    def test_gameplay_and_mixed_screens_do_not_write_a_stat(self):
        self.assertEqual(screen_kind('Condição de fuga\n3:30\n200000\n1'),'gameplay')
        self.assertIsNone(screen_kind('Random text 200000 03:30'))
        self.assertIsNone(screen_kind('Saque da partida\nInventário Mochila de Aventura'))
