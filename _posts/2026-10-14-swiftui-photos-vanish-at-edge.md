---
title: "Fixing 48 MB thumbnails hid a SwiftUI grid bug for eleven weeks"
description: "Chat photos in SwiftUI vanished when a bubble touched the screen edge. Downsampling fixed it in July. A LazyVGrid in a flipped list brought it back."
date: 2026-10-14 20:18:00 +0900
categories: [iOS]
tags: [swiftui, imageio, lazyvgrid, gpu-memory, image-loading]
lang: en
hidden: false
mermaid: false
ref: swiftui-photos-vanish-at-edge
permalink: /posts/swiftui-photos-vanish-at-edge/
math: false
---

In my SwiftUI chat app, if a photo bubble touched the top or bottom edge of the screen by one pixel, every photo on screen disappeared at once. It only happened on a real iPhone. In July I shipped three fixes within ten hours, and the third went into my notes as the cause: thumbnails decoded at full resolution, about 48 MB each.

In October the symptom came back, and this time the cause was one my notes had ruled out. A lazy grid working in flipped coordinates decided that tiles on the edge were off screen.

## A flipped list with photo grids inside

The app is a private chat app, built with SwiftUI and Swift 6 for iOS 26. The timeline uses the usual inverted-list trick, so the newest message sits at the bottom and new messages don't shift the scroll position:

```swift
ScrollView {
    LazyVStack {
        ForEach(messages.reversed()) { message in
            MessageRow(message)
                .scaleEffect(x: 1, y: -1)   // flip each row back
        }
    }
}
.scaleEffect(x: 1, y: -1)                   // flip the whole list
```

A photo message is a bubble with one to ten tiles, laid out by a `LazyVGrid` with one or two columns. Each tile drew its image with `scaledToFill` inside a rounded clip.

Scrolling until a photo bubble was partly off screen blanked every photo tile on screen, not just the one at the edge. Text bubbles stayed. The simulator never showed it.

## Three fixes in ten hours

All three commits are from the same day, between 01:09 and 11:07.

| commit time | hypothesis | change | result on device |
|---|---|---|---|
| 01:09 | the overflow layer from `scaledToFill` is dropped when a transformed parent clips it partially | `.clipped()` on the image | still vanished |
| 10:31 | SwiftUI culls the image layer whole under the row transform | flatten the tile with `.drawingGroup()` | still vanished |
| 11:07 | full-resolution decode blows the GPU texture budget | downsample with ImageIO, long edge 1600 px | shipped as the fix |

The first two were rendering theories, and since the simulator never failed, I couldn't test either one there. I took that as a hint. If something only breaks on hardware, I figured, the hardware must be short on some resource. That line of thought found the decode problem, and it's also why I stopped looking.

## Camera photos at 48.8 MB each

The third theory came from looking at which photos broke. Small images were fine and real camera photos weren't. The thumbnail loader called `UIImage(data:)` on the original file, so a 12-megapixel photo became a 4032 × 3024 bitmap:

| decode | pixels | bytes at 4 B/px |
|---|---|---|
| original 4032 × 3024 | 12.2 M | 48.8 MB |
| long edge 1600 (1600 × 1200) | 1.92 M | 7.7 MB |
| long edge 1200 (1200 × 900), October | 1.08 M | 4.3 MB |

A screen with a few photo bubbles holds hundreds of megabytes of textures at full resolution. My explanation at the time went like this. When a row crossed the edge and got composited again, the GPU had to evict textures to make room, and it evicted all of them.

I downsampled with ImageIO:

```swift
import ImageIO
import UIKit

func thumbnail(from data: Data, maxPixel: CGFloat) -> UIImage? {
    guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,   // ignore tiny embedded thumbs
        kCGImageSourceCreateThumbnailWithTransform: true,     // apply EXIF orientation
        kCGImageSourceShouldCacheImmediately: true,           // decode now, not at first draw
        kCGImageSourceThumbnailMaxPixelSize: maxPixel,
    ]
    return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
        .map(UIImage.init(cgImage:))
}
```

The full-screen viewer kept its own path that decoded the original, so tapping a photo still showed full quality. In my gotchas file I wrote "misdiagnosis: culling and transform; cause: decode size." The `.drawingGroup()` from the second attempt stayed in the code.

## The same blank tiles in October

In October I was building a photo viewer with swipe-to-dismiss and a disk cache, and the photo bubbles started vanishing at the edge again. The two files involved hadn't changed since July except for a color refresh. Either the July fix had never been complete, or something new had put large images back on screen. It turned out to be both.

The viewer was the new part. It decoded originals and stored them in the same in-memory cache as the thumbnails, under the same URL key. After you opened a photo and closed it, the bubble's tile looked up its URL and got the 12-megapixel image back. The July downsampling still ran, but only on a cache miss.

The grid had been there all along. In that day's commit message I described it this way: a `LazyVGrid` inside the flipped lazy list computed its visible region in flipped coordinates. When a bubble touched the screen edge, it treated the tiles as off screen and dropped them.

## Two caches and an eager Grid

I replaced the lazy grid and split the cache:

```swift
// 1. Eager grid: at most ten tiles, cheap to build every time.
Grid(horizontalSpacing: 4, verticalSpacing: 4) {
    ForEach(rows, id: \.first?.id) { row in        // media chunked into rows of 1 or 2
        GridRow {
            ForEach(row) { item in Tile(item) }
            if row.count < columns {
                Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
            }
        }
    }
}

// 2. Separate caches so a thumbnail lookup can never return an original.
let thumbnailCache = ImageCache(costLimit: 80 * 1024 * 1024)
let fullSizeCache  = ImageCache(costLimit: 150 * 1024 * 1024)
```

The third change lowered the thumbnail cap from 1600 to 1200 px. I'd sized 1600 for a full-width tile, but a single-tile bubble is about 260 pt wide, or 780 px at 3x. At 1200 there's still room to spare, and each tile drops from 7.7 MB to 4.3 MB, roughly half.

## A decoder pinned to the main actor

Thirty-eight minutes after that commit I fixed another regression in the same build. Opening a chat with many photo bubbles froze the screen and dropped touches. The loader called the decoder from a detached task, but the project builds with `MainActor` as the default isolation, so the decoder type was main-actor isolated without my writing it anywhere. Every downsample hopped back to the main thread. I marked the decoder `nonisolated` and lowered bubble thumbnail work to `.utility` priority, so it ran behind scrolling and taps.

## Replacing 475 lines with Nuke

By the end of October my image code had grown into a disk cache, a downloader that merged duplicate requests and cancelled work for tiles that scrolled away, two memory caches, and the ImageIO decoder. I replaced all of it with Nuke 13. Its pipeline does the same jobs: disk and memory caching of originals and resized images, request coalescing, cancellation, and ImageIO downsampling. Across the four iOS media files that changed most, about 475 lines of my code went away and a 181-line wrapper took their place. I accepted two costs: following Nuke's major versions, and every photo downloading once more after the update.

## What the July note should have said

The July note cost me more than any of the fixes. I'd found one real cause, written it down as the cause, and from then on that entry told me, and the coding agents I work with, not to look at culling. The simulator "agreeing" proved nothing, since it had never reproduced the bug.

A gotchas entry of mine now has two separate lines: what fixed the symptom, and what evidence ruled each other suspect out. For this bug I also keep one check. If small images work and large ones break only on hardware, I suspect decode size and memory before layout. And every image size gets its own cache key. Nuke keys resized images by size, so a thumbnail lookup can't come back with an original, whichever path filled the cache first.
