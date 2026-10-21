import unittest
from shortcut_keys import compile_shortcuts, matching_actions, DEFAULT_SHORTCUTS


class ShortcutTests(unittest.TestCase):
    def test_save_is_configurable_and_distinct_from_capture(self):
        from shortcut_keys import GLOBAL_ACTIONS,ACTION_IDS
        self.assertIn('save',GLOBAL_ACTIONS)
        self.assertEqual(compile_shortcuts(DEFAULT_SHORTCUTS)['save'],(120,6))
        self.assertNotEqual(ACTION_IDS['save'],ACTION_IDS['capture'])
        self.assertIsNone(compile_shortcuts({**DEFAULT_SHORTCUTS,'save':''})['save'])
        with self.assertRaisesRegex(ValueError,'conflicts'):
            compile_shortcuts({**DEFAULT_SHORTCUTS,'save':'Ctrl+Shift+F8'})
    def test_map_poll_fallback_and_late_hook_are_one_physical_press(self):
        from shortcut_keys import ObservedKeyTaps
        taps=ObservedKeyTaps()
        self.assertEqual(taps.presses([],False,1.0),0)
        self.assertEqual(taps.presses([],True,1.1),1)
        self.assertEqual(taps.presses([1.05],True,1.2),0)
        self.assertEqual(taps.presses([],False,1.3),0)
        self.assertEqual(taps.presses([1.35],True,1.4),1)

    def test_short_native_tap_and_next_sampled_tap_stay_separate(self):
        from shortcut_keys import ObservedKeyTaps
        taps=ObservedKeyTaps()
        self.assertEqual(taps.presses([1.0],False,1.04),1)
        self.assertEqual(taps.presses([],True,1.10),1)
        self.assertEqual(taps.presses([1.08],False,1.15),0)

    def test_semicolon_uses_keyboard_layout_and_only_matches_in_game(self):
        keys=compile_shortcuts(DEFAULT_SHORTCUTS,resolve_char=lambda c: (0xBF,0) if c==';' else (ord(c.upper()),0))
        self.assertEqual(keys['overlay'],(0xBF,0))
        self.assertEqual(matching_actions(keys,0xBF,0,False),[])
        self.assertEqual(matching_actions(keys,0xBF,0,True),['overlay'])
        self.assertEqual(matching_actions(keys,0xBF,2,True),[])

    def test_conflicts_are_checked_after_key_names_are_resolved(self):
        with self.assertRaisesRegex(ValueError,'conflicts'):
            compile_shortcuts({**DEFAULT_SHORTCUTS,'overlay':'Control+Shift+F8'})

    def test_disabled_actions_and_changed_map_keys_route_by_action(self):
        keys=compile_shortcuts({**DEFAULT_SHORTCUTS,'capture':'','clear':'','overlay':'F2','map':'Tab','close_map':'Ctrl+Q'})
        self.assertIsNone(keys['capture'])
        self.assertEqual(matching_actions(keys,9,0,True),['map'])
        self.assertEqual(matching_actions(keys,81,2,True),['close_map'])
        self.assertEqual(matching_actions(keys,113,0,True),['overlay'])

    def test_character_requiring_shift_keeps_that_requirement(self):
        keys=compile_shortcuts(DEFAULT_SHORTCUTS,resolve_char=lambda c:(0xBC,4) if c==';' else (ord(c.upper()),0))
        self.assertEqual(matching_actions(keys,0xBC,0,True),[])
        self.assertEqual(matching_actions(keys,0xBC,4,True),['overlay'])

    def test_map_observation_still_sees_m_while_sprint_shift_is_held(self):
        keys=compile_shortcuts(DEFAULT_SHORTCUTS)
        self.assertEqual(matching_actions(keys,77,4,True),['map'])


if __name__=='__main__':unittest.main()
