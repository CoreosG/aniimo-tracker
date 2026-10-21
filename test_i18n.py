import unittest
from i18n import tr,set_language,display_day


class TranslationTests(unittest.TestCase):
    def tearDown(self):set_language('en')

    def test_english_remains_available_after_portuguese(self):
        set_language('pt-BR');self.assertEqual(tr('Save run'),'Salvar partida')
        set_language('en');self.assertEqual(tr('Save run'),'Save run')

    def test_compact_overlay_preserves_layout_and_shortcut(self):
        set_language('pt-BR')
        self.assertEqual(tr('Chaos 32 · Map confirmed\nLoot 420.9K · Pts 370 · Ctrl+Shift+F9 save'),
            'Caos 32 · Mapa confirmado\nSaque 420,9K · Pts 370 · Ctrl+Shift+F9 salvar')

    def test_brazilian_numbers_dates_and_singular_labels(self):
        set_language('pt-BR')
        self.assertEqual(tr('Balance 1,234,567.50'),'Saldo 1.234.567,50')
        self.assertEqual(tr('2026-10-20T05:16:51'),'20/10/2026 05:16:51')
        self.assertEqual(display_day('2026-10-20'),'20/10')
        self.assertEqual(tr('1 failed'),'1 derrota')

    def test_unknown_text_and_disabled_language_fail_safely(self):
        set_language('pt-BR');self.assertEqual(tr('a9993cf6_auto.png'),'a9993cf6_auto.png')
        with self.assertRaises(ValueError):set_language('not-a-language')
