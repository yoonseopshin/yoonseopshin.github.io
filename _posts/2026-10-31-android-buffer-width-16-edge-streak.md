---
title: "Buffer widths that weren't multiples of 16 left a light streak on a Fold7"
description: "Release-build switches traced an Android-only bloom streak to buffer width alignment, and 60 Hz pacing fixed a drag stutter that measured about 80 fps."
date: 2026-10-31 01:28:50 +0900
categories: [Graphics]
tags: [android, filament, opengl-es, frame-pacing, surfaceview]
lang: en
hidden: false
mermaid: false
ref: android-buffer-width-16-edge-streak
permalink: /posts/android-buffer-width-16-edge-streak/
math: false
---

On the cover screen of a Galaxy Z Fold7, the 3D room in my app had a smear of white, green, and purple light along the right edge. Turning off bloom removed it. So did changing the render buffer's width from 1080 to 832 pixels, while 824 still showed it. The widths that worked were multiples of 16.

That same night I also fixed a stutter on the same screen. Dragging to look around felt uneven even though the frame counter said about 80 fps. Both fixes came from switches I added that night, which turn rendering features off in a release build without rebuilding.

## A Filament room in a SurfaceView

The app's home screen is a small 3D room rendered with Filament 1.79 through my own C++ bridge. On Android it uses the OpenGL ES backend, and this device has an Adreno GPU. The view is a `SurfaceView` inside Compose's `AndroidView`, and a `Choreographer` callback drives each frame. The same scene and the same GLB file run on iOS through Metal.

I saw both problems on the release build on the device: light on the right edge, and a drag that felt uneven. Neither had shown up in my earlier checks, and for the first one the reason is simple. My Android render checks ran on the emulator in a "plain" mode with post-processing off, and bloom is post-processing. The one effect that produced the artifact was never on in the configuration I was checking. A Mac Metal render at width 804, also not a multiple of 16, was clean.

## Switches I can flip with adb

Rebuilding to test guesses about a rendering artifact is slow, and I wanted to look at the exact build that showed the problem. So I added a few system properties that the native code reads when the 3D view is created. Properties under `debug.` can be set from `adb shell` on a normal device, which means they work on the release APK itself:

```cpp
#include <sys/system_properties.h>
#include <string>

// "debug.myapp.render.off" holds a comma list, e.g. "bloom,taa"
bool featureOff(const char* name) {
    char value[PROP_VALUE_MAX] = {0};
    if (__system_property_get("debug.myapp.render.off", value) <= 0) return false;
    const std::string list = "," + std::string(value) + ",";
    return list.find("," + std::string(name) + ",") != std::string::npos;
}

void applySwitches(filament::View* view) {
    if (featureOff("bloom")) {
        auto bloom = view->getBloomOptions();
        bloom.enabled = false;
        view->setBloomOptions(bloom);
    }
    if (featureOff("post")) view->setPostProcessingEnabled(false);
    // same pattern for taa, ao, shadows, idle-skipping
}
```

Two more properties set a density cap for the buffer and turn on a log line with GPU time p50 and p95 every N frames. I set a property, reopen the screen, and look at the same spot:

```bash
adb shell setprop debug.myapp.render.off bloom
adb shell setprop debug.myapp.render.log 300   # GPU p50/p95 every 300 frames
```

## Five buffer widths

I switched effects off one at a time, and the streak survived everything except turning bloom off. So bloom was spreading the problem. The clean edge in the Metal render and at other widths suggested it wasn't creating it. Bloom blurs bright pixels over a wide area, so one bad column at the edge turns into a visible smear.

Then I varied the buffer width:

| buffer width | multiple of 16 | right-edge streak |
|---|---|---|
| 1080 | no (67.5 × 16) | yes |
| 824 | no (51.5 × 16) | yes |
| 784 | yes | no |
| 800 | yes | no |
| 832 | yes | no |

My reading is that when the width isn't 16-aligned, the last column of a post-processing buffer holds garbage on this GPU and driver, and bloom smears it.

## A fixed buffer size aligned to 16

I gave the `SurfaceView` a fixed buffer size that's always a multiple of 16. While I was there, I capped the render density at 2, the same cap the iOS host uses. The compositor scales the buffer up to the view.

```kotlin
private const val MAX_DENSITY = 2f
private const val ALIGN = 16

fun bufferSize(view: View): Pair<Int, Int> {
    val density = view.resources.displayMetrics.density
    val scale = if (density <= MAX_DENSITY) 1f else MAX_DENSITY / density
    fun align(v: Float) = maxOf(ALIGN, (v / ALIGN).roundToInt() * ALIGN)
    val width = align(view.width * scale)
    val height = align(width * view.height.toFloat() / view.width)
    return width to height
}

// in surfaceChanged / on layout change:
val (w, h) = bufferSize(surfaceView)
surfaceView.holder.setFixedSize(w, h)
```

Rounding each side on its own changes the aspect ratio a little. For these sizes the distortion stayed under 0.5%.

Two details took some care. Once the buffer is smaller than the view, touch handling for walking and tapping objects has to use the view's size, so the host now receives both sizes. And folding or unfolding the phone changes the view size without changing the fixed buffer size, so `surfaceChanged` doesn't fire. A layout-change listener on the `SurfaceView` recomputes the size in that case.

The roughness score of the rightmost column went from 24.4 before the change to 5.3 after, inside the 4 to 6 range of interior columns.

## 13 to 20 ms frames on a 120 Hz screen

The cover screen runs at 120 Hz, and `Choreographer` called the frame callback on every vsync, every 8.3 ms. While dragging, the GPU needed 13 to 20 ms per frame, and its clock sat at 222 to 443 MHz out of a 1,200 MHz maximum, so it wasn't even running fast. A frame that takes longer than one vsync slot goes out at the next free slot, so frame intervals came out as a mix of 8, 16, and 24 ms. On paper about 80 fps beat 60. In the hand it felt worse.

The room also kept rendering when nothing moved, at 69 fps while idle.

I measured presentation with SurfaceFlinger's timestats over three drags, before and after:

| metric (3 drags, SurfaceFlinger timestats) | before | after |
|---|---|---|
| frame rate while dragging | ~80 fps | 59–60 fps |
| share of 16 ms intervals | 45% | 70–77% |
| share of 8 ms intervals | 51% | n/a |
| 8 ms + 24 ms pairs | n/a | 11–15% |
| intervals over 25 ms | n/a | 0.2–1.2% |
| frames rendered while idle | 69 fps | 0 |

I changed three things:

- The frame callback skips vsyncs until about 16.7 ms have passed, with half a vsync of tolerance so jitter doesn't drop a frame.
- The surface declares itself a 60 fps source, so the display can drop to 60 Hz when nothing else needs 120.
- The native side renders only when something changed, then keeps going for 8 more frames so temporal anti-aliasing can settle. The iOS host already worked this way.

```kotlin
private const val FRAME_NS = 16_666_667L
private const val HALF_VSYNC_NS = 4_166_667L   // half of a 120 Hz slot

override fun doFrame(vsyncNanos: Long) {
    if (last != 0L && vsyncNanos - last < FRAME_NS - HALF_VSYNC_NS) {
        choreographer.postFrameCallback(this)  // too early: wait for the next vsync
        return
    }
    last = vsyncNanos
    renderer.renderIfDirty(vsyncNanos)          // native side skips when nothing changed
    choreographer.postFrameCallback(this)
}

// once, when the surface is created (API 30+)
surface.setFrameRate(60f, Surface.FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)
```

I tried three other things and left them out. `setPresentationTime` and ADPF performance hints both moved the numbers by less than the difference between repeated runs. Lowering the resolution by 1.5x left GPU time where it was, so the scene isn't pixel-bound on this device. That matched iOS, where dynamic resolution barely helped this scene either.

## GPU time is still over budget

The pacing fix made frames even. It didn't make them cheap. GPU time during interaction is still 15 to 16 ms at p50 and 19 to 21 ms at p95, against the 12 ms budget I set for this scene.

## Turning effects off on the shipping build

The property switches were the cheapest thing I built that night, and I'd add them before the first complaint next time. Turning one effect off at a time on the release build narrowed "there's weird light on the right" down to "bloom plus a width that isn't a multiple of 16" in a handful of runs.

My emulator renders were real renders, but of a configuration without post-processing, and the artifact was entirely in post-processing. A screenshot comparison covers only the features that were on when it was taken.
