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
