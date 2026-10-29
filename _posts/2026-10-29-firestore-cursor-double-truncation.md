---
title: "Half of my Firestore page cursors pointed just below their own document"
description: "Truncating a Double-based Date into Firestore Timestamp parts puts about half of all cursors below the stored value. Rounding to microseconds fixes it."
date: 2026-10-29 19:35:15 +0900
categories: [Kotlin Multiplatform]
tags: [firestore, swift, kotlin-multiplatform, pagination, floating-point]
lang: en
hidden: false
mermaid: false
ref: firestore-cursor-double-truncation
permalink: /posts/firestore-cursor-double-truncation/
math: false
---

My chat app builds each page cursor from the last message of the previous page. For about half of all messages, that cursor came out a fraction of a microsecond earlier than the message itself. Firestore then treated the message as "after the cursor" and sent it again at the top of the next page, and with `limit(1)` paging never moved.

I found it while moving chat decoding from Swift into shared Kotlin Multiplatform code. The port didn't introduce the bug. The Swift code had built cursors this way since July.

## A cursor that crosses the Swift bridge

The app is a small private chat app. Its iOS client uses the Firebase iOS SDK 11.15 and the shared module is Kotlin 2.4. Search and the history view read a full-history index that loads messages in ascending `createdAt` order, with the document ID as a tie-breaker. Each page continues with `startAfter([createdAt, id])` from the last message it received.

The Swift client wrote older messages with `setData(from:)`, which encodes a Swift `Date` as a Firestore `Timestamp`. Firestore keeps timestamps to the microsecond, so those `createdAt` values carry six digits below the second. The iOS screen model holds `createdAt` as a `Date`, which is a `Double` of seconds. A cursor value makes this trip:

```text
Firestore          shared Kotlin         Swift screen model       next query
createdAt   --->   (ms, nanos)   --->    Date (Double)    --->    Timestamp(seconds, nanos)
exact µs           exact                 nearest Double           <- this step truncated
                                         (within 119 ns)
```

The bug was in the last step. I fixed a different precision problem before I found it.

## Sub-millisecond nanos in the shared type

The shared Kotlin code started with a timestamp type that held only epoch milliseconds. I'd flagged the risk in the plan for the chat port before writing any code. If the cursor is cut to milliseconds, a message stored at `…123456 µs` sorts after a cursor of `…123000 µs`, so the boundary message comes back on the next page and a `limit 1` query returns the same message forever.

The first commit gave the shared type a field for the part below a millisecond:

```kotlin
data class Timestamp(val epochMs: Long, val nanosOfMilli: Int) {
    constructor(epochMs: Long) : this(epochMs, 0)

    val seconds: Long get() = epochMs.floorDiv(1000L)
    val nanos: Int get() = (epochMs.mod(1000L) * 1_000_000L).toInt() + nanosOfMilli

    companion object {
        fun of(seconds: Long, nanos: Int) =
            Timestamp(seconds * 1000L + nanos / 1_000_000, nanos % 1_000_000)
    }
}
```

The secondary constructor kept every existing Swift call site compiling, since most records still use milliseconds only. I added six golden cases to the shared contract file: sub-millisecond preserved, zero omitted, negative seconds, two write cases, and a JSON round trip. Five failed before the change and all six passed after. That fixed the Kotlin side but not the cursor.

## `Timestamp(date:)` truncates

I had the finished port reviewed, and the reviewer went back to the Swift side of the bridge. When the app asked for the next page, it turned the last message's `Date` into parts with Firebase's own initializer:

```swift
let stamp = Timestamp(date: last.createdAt)   // fraction is truncated
query.start(after: [stamp, last.id])
```

In the SDK, `Timestamp(date:)` calls `modf` on `timeIntervalSince1970` and casts `fraction * 1e9` to `int32_t`, and that cast truncates. If the `Double` held the microsecond value exactly, truncating would be harmless. It can't hold it. Near 1.7 × 10⁹ seconds, adjacent `Double` values are 2⁻²² s apart, about 238 ns. The `Double` that `dateValue()` produces is the nearest representable number, so about half the time it sits a little above the stored microsecond and the rest of the time a little below.

Above, truncation gives the stored value or slightly more. Below, it stays below. These are illustrative values at the largest error:

```text
stored           ...123456000 ns
Double (below)   ...123455881 ns  -> truncated cursor ...123455881 ns  <  stored
Double (above)   ...123456119 ns  -> truncated cursor ...123456119 ns  >= stored
```

`startAfter` compares `(createdAt, id)`. In the first case the boundary message's `createdAt` is greater than the cursor's, so the message counts as "after" the cursor and comes back.

The reviewer ran 100,000 random stored values through the old conversion, and 50,203 didn't come back as the value they started from. The same `Timestamp(date: cursor.createdAt)` call was in the Swift pagination code from July and in the ascending range query I'd added five days before the port.

## Rounding to the microsecond

The `Date` in the screen model was staying for this port, so I had to make the `Date`-to-parts conversion exact. That's possible because Firestore stores microseconds and the `Double` error is far below half a microsecond. When I re-ran the full round trip for 2017–2030 dates while writing this, the largest error was 119 ns. Rounding to the nearest microsecond gets the stored value back. So the `Double` was precise enough, and truncating was what lost the value.

```swift
enum CursorTime {
    /// Seconds since 1970 -> (epoch ms, nanos below the ms), rounded to the microsecond.
    static func split(_ t: TimeInterval) -> (ms: Int64, nanosOfMilli: Int32) {
        var seconds = t.rounded(.down)
        var micros = ((t - seconds) * 1_000_000).rounded()
        if micros >= 1_000_000 {          // 0.9999996 s rounds into the next second
            seconds += 1
            micros -= 1_000_000
        }
        let us = Int64(micros)
        return (Int64(seconds) * 1000 + us / 1000, Int32(us % 1000) * 1000)
    }
}
```

Taking whole seconds with `rounded(.down)` first keeps the fraction non-negative for dates before 1970, which matches Firestore's representation of negative seconds with positive nanos. The `micros >= 1_000_000` branch handles a fraction that rounds up to a full second.

Every place that turns a `Date` into shared time goes through this function now: page cursors, range filters, aggregate count bounds, and writes. Writes changed a little as a result. The old path truncated to nanoseconds and let the server cut to microseconds, while the new one rounds to microseconds before sending. A newly written `createdAt` can differ by one microsecond from what the old code would have stored. It's an intended behavior change, and I documented it.

## A 100,000-value round-trip script

The check is a standalone Swift script that `swiftc` compiles together with the one app source file holding `split`. I didn't use an XCTest target. Its core loop:

```swift
var mismatches = 0
for _ in 0..<100_000 {
    let s = Int64.random(in: 1_500_000_000...1_900_000_000)
    let us = Int64.random(in: 0..<1_000_000)
    let date = TimeInterval(s) + TimeInterval(us * 1000) * 1e-9   // like dateValue()
    let (ms, nanos) = CursorTime.split(date)
    if ms != s * 1000 + us / 1000 || Int64(nanos) != us % 1000 * 1000 { mismatches += 1 }
}
print("cursor-time: \(mismatches) mismatches / 100000")
exit(mismatches == 0 ? 0 : 1)
```

It also checks three fixed edge cases (−0.5 s, 0, and −1.000001 s) and exits non-zero on any mismatch.

| conversion | mismatches in 100,000 samples |
|---|---|
| `Timestamp(date:)` truncation (old) | 50,203 |
| microsecond rounding (new) | 0 |

## The same mistake in milliseconds

Earlier the same day, a review of another part of the port had turned up the same mistake one level up. Most shared rules work in epoch milliseconds, and the bridge computed them as `floor(timeIntervalSince1970 * 1000)`. A `Date` built from a millisecond value could come back one millisecond short, because `ms / 1000` isn't exact as a `Double` and the product can land just under the integer. That review counted 1,857 such losses in 200,000 values.

It mattered for calendar events. Whether the app sends a "time changed" notification depends on comparing the old and new times in milliseconds, so an edit that touched only the title could look like a time change. The fix keeps the floor, so two instants inside the same millisecond still compare equal, and snaps to the nearest integer when the product is within 0.001 ms of it:

```swift
var epochMillis: Int64 {
    let ms = timeIntervalSince1970 * 1000
    let nearest = ms.rounded()
    return Int64(abs(ms - nearest) < 1e-3 ? nearest : ms.rounded(.down))
}
```

With the snap, a `Date` built from a millisecond value returns that millisecond. I re-ran a 200,000-value sample over several value ranges against the snapped version, and it lost none.

## Testing from what's in the database

Once the shared `Timestamp` could hold nanoseconds, I'd considered the cursor problem solved. The golden tests agreed because they started from integer seconds and nanoseconds. The value that broke had gone through a `Double` on the other side of the bridge, and no test fed a stored value through that path. My round-trip tests now start from a value as Firestore stores it and pass through every representation the app uses on the way back.

Truncating is fine when the input is exact. After floating point, I round to the resolution of whatever stores the value, here Firestore's microsecond. When I review code now, I look for `rounded(.down)`, `floor`, and integer casts near any `Date` or `Double` that feeds a key, a cursor, or an equality check.
