---
title: "Moving a Blender room to Filament let the sky in three times"
description: "An outdoor HDRI, a diorama's missing wall and two quality tiers that disagreed on shadows each let the sky into a Filament room on iOS."
date: 2026-10-30 18:17:07 +0900
categories: [Graphics]
tags: [filament, ios, ibl, shadows, blender, rendering]
lang: en
hidden: false
mermaid: false
ref: filament-room-sky-leaks
permalink: /posts/filament-room-sky-leaks/
math: false
---

Every white area I chased in my 3D room turned out to be the sky. The first time it lit the whole interior. Later it showed through a wall that had never existed, and in the end it was the sun coming straight through a wall I'd told not to cast shadows. The last two only appeared while I was dragging the camera, so none of my harness screenshots ever caught them.

## A Metal room and a still-frame harness

The room lives in a personal iOS app. I modeled and lit it in Blender, and until this port a hand-written Metal renderer drew it with lighting baked in Cycles. I moved it to Filament 1.79.0 so the same scene could later run on Android, bridged into iOS through Objective-C++. The room is about 4 m across. Device numbers below come from an iPhone 13, simulator numbers from an iPhone 17 Pro simulator on iOS 26.5, all built on one Mac.

Next to the app I kept a Mac offscreen harness. It renders day and night PNGs from the same GLB and the same C++ header that holds every lighting value, and I treated its captures as a stand-in for what the app shows.

## The outdoor HDRI lit the whole room

I started with the obvious move: take the HDRI the Blender scene used for its world and hand it to Filament as image-based lighting. Depth appeared, but the floor and ceiling blew out to white-yellow and the walnut furniture went a muddy purple. Constant spherical-harmonics fill light gave the opposite result. Everything looked flat.

Filament's IBL models an environment infinitely far away, and it knows nothing about walls or ceilings. So the outdoor sky went into the diffuse and specular lighting of every surface in the room, and the clearcoat floor mirrored it. GTAO hid some of that, nowhere near enough.

I stopped treating the room as if it were outdoors. From a point inside the room I baked a 360° probe in Cycles with the original Blender light rigs for day and night, which takes about 20 seconds. I ran that through `cmgen` for the IBL, kept the HDRI only as the skybox seen through the windows, and added the sun as its own directional light. Reflections now show the room, and indirect color follows the original GI. A single probe point means indirect light doesn't vary across the room. Lightmaps are the next step for that.

The same afternoon had two smaller traps. gltfio returns `nil` for every node name unless you pass a `NameComponentManager` to `AssetLoader::create`, so picking quietly finds nameless entities. Blender's glTF exporter drops emission and writes Generated texture coordinates as `texCoord: -1`, which gltfio refuses to load. With 1024 px textures and Draco, the mobile GLB went from 48.48 MB to 7.39 MB.

## 57 to 86 ms per frame while dragging

An early TestFlight build drew SSR, high-quality GTAO with bent normals, PCSS soft shadows, bloom and TAA on every frame, dragging included. On an iPhone 13 that came to 57 to 86 ms of GPU time per frame. I split rendering into two tiers: an interactive one while the user drags or walks, and a still one the view settles back to once input stops. The first interactive tier turned off SSR, dropped AO to low quality without bent normals and allowed dynamic resolution. Interactive frames came down to about 14.5 ms.

The harness kept rendering the still tier. A PNG is a still frame.

## White while dragging, clean when still

On the next TestFlight build I saw large white areas whenever I dragged to look around. Still frames looked fine.

I reproduced it in a simulator with a synthetic drag of about ±67°, recorded the screen and pulled one frame per second. Each time the view turned left, the left half of the screen washed white. My suspects were the near plane (0.05 m), dynamic resolution, a TAA history reset and empty frames while textures uploaded asynchronously. None of them showed up in the recorded frames. There were black frames during loading, but they came before the scene existed and weren't white.

Then I checked the GLB node bounds around the eye position, and there was no wall on that side. The Blender room is a diorama. Its face toward the camera is left open on purpose so sky light fills the shadows, which makes sense when the camera stands outside the box. My first-person start position was 0.35 m from that open face:

```
   top view                 back wall
            +-----------------------------+
   window   |                             |
   wall  -> |            room             |
   (sun)    |                             |
            |                    eye *    |
            +  -  -  -  -  -  -  -  -  -  +   <- 0.35 m from the eye: no wall
                     day HDRI skybox          (the sun also leans in from here)
```

Turn left or back and the bright day skybox filled the screen. The Metal version never showed it because its room sat inside a larger scene that closed that face.

The export script now adds a front wall. The sun enters from that side, so a shadow-casting wall would have made the room darker than the original, and I turned shadow casting off on the new wall to keep the lighting where it was. Still-frame PSNR against the earlier captures was 84 dB for day and 81 dB for night. I re-recorded the same drag and the white wash was gone. On an iPhone 13 the interactive tier measured 14.3, 14.2 and 15.3 ms GPU p50 over three runs, in the same range as the 14.3 and 14.5 ms from before, so the extra wall didn't change the interactive cost.

## Cutting the interactive tier to 11 ms

14.5 ms p50 was still over my 12 ms budget, and that budget is for p95. An hour later I cut the interactive tier further: PCF shadows instead of PCSS, AO off, bloom and TAA off, one shadow cascade, a 1024 shadow map, no contact shadows. Two device runs gave 11.0 and 10.0 ms GPU p50 (14.1 and 13.0 ms p95).

## Haze from turning AO off

That change made the whole image go milky for a moment on each transition, then snap back. I added a development flag that forces the interactive tier while the camera is still, so I could capture both tiers from the same pose. I compared the 3D area of each capture with ffmpeg's `ssim` and `signalstats` filters, then switched effects off on the still tier one at a time:

| Frame (same pose, day) | SSIM vs still | YLOW (dark end) | YAVG |
|---|---|---|---|
| Still tier | 1 | 69 | 127.3 |
| Interactive tier | 0.862 | 92 | 137.7 |
| Still, AO off only | 0.906 | 90 | 136.5 |
| Still, SSR off only | 0.979 | 75 | 129.5 |
| Still, TAA off only | 0.953 | 64 | 126.5 |
| Still, PCF instead of PCSS | 0.988 | 67 | 126.7 |

AO off on its own reproduced nearly all of the lift in the dark end. With bent normals, AO is what keeps the IBL out of places it shouldn't reach, and the interactive tier had none. I turned AO back on at low quality with bent normals, which gave SSIM 0.919 and YLOW 72, and moved on. I left the other differences between the tiers alone.

## A 110,000 lux sun through the shadowless wall

Later that day I had white patches that shook while walking or turning, and sunlight that seemed to vanish and come back. This time I wrote down what I'd measure before touching anything. No solid black or white frames. No tier-switch flicker, meaning a mean luminance change above 0.5 or an 8×8 block change above 3 on a 0 to 255 scale. No shadow-map change on a tier switch. At most 8 of mean luminance change in one frame during the day/night transition. I picked 0.5 because it's about 0.4% of a mean luminance of 130, above the TAA jitter after the fix (0.15) and below the tier switches before it (1.55).

The harness reads back every frame, and a frame where the tier switched counts as flicker if it moved past either limit:

```python
import numpy as np

def is_flicker(prev, cur, mean_limit=0.5, block_limit=3.0):
    """prev, cur: 2D uint8 luma arrays of the 3D area, camera not moving."""
    a, b = prev.astype(np.float32), cur.astype(np.float32)
    if abs(b.mean() - a.mean()) > mean_limit:
        return True
    h, w = (a.shape[0] // 8) * 8, (a.shape[1] // 8) * 8
    blocks = lambda x: x[:h, :w].reshape(h // 8, 8, w // 8, 8).mean(axis=(1, 3))
    return np.abs(blocks(b) - blocks(a)).max() > block_limit

flicker = sum(is_flicker(f[i - 1], f[i]) for i in tier_switch_frames)
```

Then I changed one setting at a time from the same pose. The big white patch went away only when I switched the interactive tier from PCF back to PCSS. It was the 110,000 lux sun coming straight through the front wall I'd made shadowless, and PCSS happened to hide it. Since the light was going through a wall, I made the wall block it.

Most of the remaining jolt on tier switches came from SSR turning on and off. Removing just that difference cut the mean luminance change per switch from 1.86 to 0.66. PCSS, shadow map size, TAA and bloom made up the rest.

## One table of allowed differences

After that I stopped letting the tiers differ in anything that changes light. They now differ only in AO quality, and that difference lives in one small table:

```cpp
struct Tier { filament::QualityLevel ao, aoFilter; };   // the only allowed differences

Tier tierFor(bool moving) {
    using filament::QualityLevel;
    return moving ? Tier{QualityLevel::LOW, QualityLevel::MEDIUM}
                  : Tier{QualityLevel::HIGH, QualityLevel::HIGH};
}

void apply(filament::View* view, const Tier& t) {
    using namespace filament;
    AmbientOcclusionOptions ao;
    ao.bentNormals = true;                 // keeps the IBL out of occluded areas
    ao.quality = t.ao;
    ao.lowPassFilter = t.aoFilter;
    view->setAmbientOcclusionOptions(ao);
    view->setShadowType(ShadowType::PCF);  // same in both tiers
    ScreenSpaceReflectionsOptions ssr;
    ssr.enabled = false;                   // same in both tiers
    view->setScreenSpaceReflectionsOptions(ssr);
    // TAA and bloom on, dynamic resolution off, 1024 shadow map: also shared
}
```

Everything else is set once for both. The front wall casts shadows now. Only the window glass and the sky planes behind the windows don't, so sunlight comes in through the window and nowhere else. The patch it made through the window clipped to white, so I lowered the sun from 110,000 to 50,000 lux.

## Day to night, and the black first frame

The day/night transition swapped the whole probe at t = 0.5, and mean luminance jumped by 58 in that one frame. I now blend the irradiance spherical harmonics every frame and interpolate sun intensity in log space. Exposure is logarithmic, and a linear blend had made the middle of the transition brighter than day:

```cpp
float3 sh[9];
for (int i = 0; i < 9; ++i) sh[i] = daySH[i] * (1 - t) + nightSH[i] * t;
auto* light = IndirectLight::Builder()
    .reflections(t < 0.5f ? dayCube : nightCube)
    .irradiance(3, sh)
    .build(*engine);
scene->setIndirectLight(light);           // and destroy the previous blended one
float sunLux = std::exp(std::lerp(std::log(daySun), std::log(nightSun), t));
```

Going from the list screen into the room also showed about 0.2 s of solid black. The host revealed the view as soon as the first frame was submitted. Drawing more frames first changed nothing. Waiting until the first frame's GPU time came back (or 30 frames, if it never does) fixed it.

## Before and after

I measured these on the Mac harness at 780×1688 and in an iPhone 17 Pro simulator:

| Metric | Before | After |
|---|---|---|
| Tier-switch flicker frames, day / night | 6 / 4 | 0 / 0 |
| Mean luminance change per tier switch, day / night | 1.55 / 3.12 | 0.017 / 0.006 |
| Shadow-map changes on tier switch | 6 | 0 |
| Largest one-frame jump, day→night / night→day | 58.3 / 58.3 | 6.2 / 5.3 |
| Black frames, list↔room, 4 transitions | 43 | 0 |
| SSIM vs Metal baseline, day / night | 0.770 / 0.682 | 0.783 / 0.679 |
| FLIP vs Metal baseline, day / night | 0.390 / 0.548 | 0.384 / 0.553 |

The temporal numbers moved a lot. The image-quality numbers barely moved, and night got slightly worse on both. I set the SSIM and FLIP thresholds from this measurement, so the before values pass them too. They catch regressions and say nothing about whether the port matches the Metal version. The original targets (SSIM ≥ 0.95, FLIP ≤ 0.05) are still far off, and most of that gap is the multi-rig baked GI the Metal version had.

I paid for the stability in still frames. They lost screen-space reflections on the floor and table, PCSS soft shadows, contact shadows and the 2048 shadow map. Night windows still look like daytime, and the LED strips don't spill light onto the walls. Both wait for lightmaps.

## Recording a drag before trusting a screenshot

An offline Blender scene is built like a stage. The environment is a backdrop, and a missing wall is fine because the camera stands outside. Filament's IBL treats that environment as light arriving from every direction, and a first-person camera puts you inside the box. I translated the scene literally three times and patched what each translation exposed.

The part I'd reuse is about the tiers. I added them for performance, and each time they differed in something that changes light or shadow (AO, shadow filtering, SSR), I got an artifact that existed only while moving. My harness only produced still frames, so for two days I compared everything against the one state that was already right. On the next scene I'd put the tier table above in the first commit, and have the harness record a scripted drag with the tier switching underneath it, scored by the flicker check, before I trusted any screenshot.
