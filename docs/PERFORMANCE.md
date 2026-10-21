# Performance on slower PCs

The tracker is a native Python/Tk desktop app. It does not keep a browser engine
running for normal tracking. The download contains the Python runtime and OCR/map
dependencies, so executable size is not a measure of idle RAM usage.

In a disposable 18-run demo ledger on the development PC, the source app used
about **73 MB working-set RAM** while idle. Over a six-second sample it consumed
about **2.9% of one logical CPU** (about 0.18% of total capacity on that 16-thread
PC). This is a short local observation, not a minimum hardware specification or
a promise for every machine. Loaded maps, captures, OCR and a long history can
increase memory and CPU use.

A repeated gameplay screenshot benchmark measured median minimap registration
at **222 ms before** versus **37 ms after** reusing its detected area. The detected
position stayed the same. Timing depends on screen resolution, minimap content,
hardware and whether recovery is needed; initial detection is still more expensive.

## Retention checks in the corrected 0.3.0 build

The audit found and fixed two sources of retained memory: localization references
kept closed screenshot dialogs alive, and two map libraries could retain every
visited layout. Dialog destruction now removes its localization references and
Tcl callbacks immediately. Each map library retains only its two most recently
used models, and each model owns a bounded 32-entry route cache; global route
keys no longer keep evicted models alive.

Disposable stress checks on the development PC:

| Scenario | Observation |
| --- | --- |
| Open/close 100 screenshot dialogs with a synthetic 1920×1080 image | 73.95 → 74.52 MB RSS; Tk image and callback counts stayed constant |
| Show the overlay 501 times | 76.5 → 76.6 MB RSS; image and canvas item counts stayed constant |
| Browse all 21 models in both libraries, twice, without forced GC | 152.6 → 153.1 MB after each sweep; four cached models total |

The same all-layout sweep retained about 1,063 MB before the cache fix. Normal
confirmed-map tracking keeps its active model warm. Revisiting an evicted layout
requires loading it again. These are targeted stress checks, not a guarantee
against every possible memory leak or an overnight soak test.

An unknown capture that compares all seven layouts can take a few extra seconds
because evicted models must be loaded again. The full-map portal detector and
normal tracking of an already confirmed layout do not use that all-layout scan.

## Controls that help

- **Map & routes → Overlay → Position updates → Low CPU (1.5s)** updates position
  less frequently than Normal (0.7s). This does not change the map shortcut.
- Use **Pause map** when navigation is not needed. Merely hiding the overlay
  does not pause recognition or party sharing.
- **Tools → Set minimap area** can help when automatic HUD detection is unreliable.
- Keep a modest overlay size. Larger map renders cost more work.

Recognition runs off the UI thread, one panel scan at a time. OpenCV uses at most
two internal threads. Accepted minimap bounds are cached, then rediscovered after
two failed matches or a resolution change; every position still needs the same
geometric validation. Manual calibration takes priority. Hidden in-app map
previews are not rendered for each gameplay position, and slider changes are
coalesced before saving to disk. The relay receives compact coordinates and map
evidence; it performs no image processing.
