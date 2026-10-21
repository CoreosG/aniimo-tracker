import gc
import unittest
import weakref

from map_engine import MapLibrary


class MapMemoryTests(unittest.TestCase):
    def test_evicted_map_and_its_cached_routes_can_be_collected(self):
        library = MapLibrary()
        model = library.model(37)
        route = model.route(0, keys=2)
        self.assertEqual(route['stops'][0], model.routes['pts'][0])
        old = weakref.ref(model)
        del model
        library.model(32)
        library.model(39)
        self.assertIsNone(old(), 'Eviction should release the map without waiting for cyclic GC')
        gc.collect()
        self.assertIsNone(old(), 'An old map must not be retained by a global route cache')
        self.assertEqual(library.model(37).layout, 37)

    def test_recent_map_is_reused_and_a_live_external_map_survives_eviction(self):
        library = MapLibrary()
        active = library.model(37)
        second = library.model(32)
        self.assertIs(library.model(37), active)
        library.model(39)
        self.assertIs(library.model(37), active)
        self.assertIsNot(library.model(32), second)
        library.model(34)
        library.model(35)
        self.assertEqual(active.route(1, keys=1)['stops'][0], active.routes['pts'][1])
