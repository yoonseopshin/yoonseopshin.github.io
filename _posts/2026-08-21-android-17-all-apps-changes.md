---
title: "Two Android 17 changes reached my app while it still targeted SDK 36"
description: "I audited only Android 17's targetSdk page. The all-apps page applies at any targetSdk, and two of its nine entries needed code changes."
date: 2026-08-21 23:08:16 +0900
categories: [Android]
tags: [android-17, targetsdk, compose, ime, applicationexitinfo]
lang: en
hidden: false
mermaid: false
ref: android-17-all-apps-changes
permalink: /posts/android-17-all-apps-changes/
math: false
---

In July I audited my app for Android 17, found zero required code changes, and left `targetSdk` at 36 on purpose so none of the new behavior would reach users yet. Three weeks later I found two Android 17 changes that applied anyway, at `targetSdk` 36, on every Android 17 device. One stops bringing the keyboard back on the search screen after a rotation. The other is a new kind of process kill that never shows up in Crashlytics. Both were on a page my audit hadn't read.

## The July audit covered one of two pages

Android splits each release's behavior changes across two pages. [Behavior changes: apps targeting Android 17](https://developer.android.com/about/versions/17/behavior-changes-17) lists what you opt into by raising `targetSdk` to 37. [Behavior changes: all apps](https://developer.android.com/about/versions/17/behavior-changes-all) lists what the platform does to every app running on Android 17, whatever its `targetSdk`.

The app is a Compose Multiplatform quiz app, shipped as four Android apps from one codebase with `minSdk` 28. On July 31 I went through the targeting page item by item against the code. It listed 15 changes then, and none needed a code change. The app uses no audio, contacts, Bluetooth, SMS, reflection or local network. It declares no orientation restriction, and its AGP and Play Billing versions were already past what Android 17 asks for. The real work was a few existing bugs that large-screen orientation freedom would make easier to hit, like quiz timer state held in plain `remember` that a rotation wiped out.

I split the migration into two steps and wrote that down as a decision record. `compileSdk` went to 37 right away, since it only opens up the API surface. `targetSdk` would wait until after what the record called the app's busiest stretch of the year. There's no staging environment, so every release is production, and users don't update immediately. The split cost one lint warning, `OldTargetApi`.

## August was the quiet month

On August 21 I came back to finish the second step and checked the premise first. The record had read an exam calendar as a traffic calendar. The exam behind the app in question has a second round in August, but that app only covers the first round, in April. Its monthly numbers peaked in April, and August was the quietest active month.

By then the claim had spread to thirteen places across docs, agent skills and memory notes. It was also holding back an unrelated store-listing release. I wrote a new decision record that supersedes the old one instead of editing it, and marked the false premise at the top of the old one so nobody cites it again.

That was embarrassing. The bigger gap turned up when I re-read the official pages.

## Nine entries that apply at any targetSdk

The all-apps page applies regardless of `targetSdk`, so the state I had picked as safe, `targetSdk` 36, had never been the Android 16 behavior I thought it was. I went through that page the same way I'd gone through the other one. On August 21 it had nine entries:

| change (all apps, Android 17) | applies to this app? | how I checked |
|---|---|---|
| IME visibility not restored after unhandled config change | yes | no `windowSoftInputMode` declared; search screen relied on the restore |
| App memory limits based on device RAM | yes | any app can be killed; the kill isn't a crash |
| Implicit URI grant restriction | no | no `ACTION_SEND`, `ACTION_SEND_MULTIPLE`, `ACTION_IMAGE_CAPTURE` or `FileProvider`; enforced from Android 18 anyway |
| Per-app keystore key limit | no | no `KeyStore` or encrypted preferences |
| SMS OTP protection (delayed delivery, now also WebOTP) | no | no SMS |
| Cross-profile loopback blocked | no | no loopback traffic |
| Touchpad relative events under pointer capture | no | no `requestPointerCapture` |
| Background audio hardening | no | no audio APIs |
| Bluetooth autonomous re-pairing | no | no Bluetooth |

When I re-checked on October 31 the page had ten entries. The new one is a deprecation plan for `usesCleartextTraffic`. The targeting page had grown from 15 to 17 in the same time.

## The search keyboard after a rotation

The all-apps page says: "Beginning with Android 17, when the device's configuration changes (for example, through rotation), and this is not handled by the app itself, the previous IME visibility is not restored." An app that wants the keyboard after the change has to ask for it, either with `android:windowSoftInputMode="stateAlwaysVisible"` or from code.

The search screen auto-focuses its field once, after the entry transition settles, and opens the keyboard. A `rememberSaveable` flag records that the auto-focus already happened. I added it so a rotation wouldn't push the keyboard back at someone who had dismissed it. Before Android 17 the flag survived the rotation, the screen correctly didn't ask for focus again, and the system restored the keyboard by itself for anyone who'd had it open. On Android 17 the system stops doing that. Every rotation would have taken the keyboard away, including from people who had left it open.

One flag had been answering two questions: did the screen auto-focus already, and did the field have focus. I split them, and only the second one decides whether to restore:

```kotlin
var hasAutoFocused by rememberSaveable { mutableStateOf(false) }
var hadFocus by rememberSaveable { mutableStateOf(false) }
// Read once: "did this composition start focused", not "is it focused now".
val restoreFocus = remember { hadFocus }

LaunchedEffect(transitionSettled) {
    if (!transitionSettled) return@LaunchedEffect
    if ((autoFocus && !hasAutoFocused) || restoreFocus) {
        hasAutoFocused = true
        focusRequester.requestFocus()
        keyboardController?.show()
    }
}

SearchField(
    focusRequester = focusRequester,
    onFocusChange = { focused -> hadFocus = focused },
)
```

I'd have gotten the `remember { hadFocus }` line wrong. If the effect read the live `hadFocus`, dismissing the keyboard would flip it to `false`, focusing would flip it back, and the condition would run again on every focus change. Read once at entry, it describes the previous configuration and stays put.

I had two cheaper options. Turning `hasAutoFocused` back into a plain `remember` is a one-word change, but then the keyboard reopens on someone who had closed it, which is what the flag was there to stop. Declaring `stateAlwaysVisible` in the manifest would change every screen in the app. Splitting the flag kept the change inside the one screen that depended on the restore.

In October I made the main activity handle orientation and window-size changes itself, for unrelated layout reasons. Rotation no longer recreates the activity, so it doesn't take this path anymore. Dark mode, font scale and locale changes still recreate it, and for those the fix still carries the keyboard across.

## Reading memory-limit kills from the exit history

The second change: "Android 17 introduces app memory limits based on the device's total RAM." An app that crosses its limit shows up afterwards in the process exit history, which is where the page tells you to look. It's a system kill, not a crash. Nothing in the app is running to notice it, so Crashlytics never gets a report. The user sees the app vanish, and the next launch is a cold start.

The exit history is the only record, and the app can read it only after the fact. The page says what to look for: "the exit reason will be `REASON_OTHER` and the description will contain the string `"MemoryLimiter:AnonSwap"`." So at each launch the app reads its history and reports any new memory-limit kill as an analytics event. I put the decision logic in common code so I could unit test it, and wrapped the platform read in a thin Android function:

```kotlin
fun reportMemoryLimitKills(context: Context, prefs: SharedPreferences) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return  // API 30+
    val am = context.getSystemService(ActivityManager::class.java) ?: return
    val since = prefs.getLong("watermark", 0L)
    val exits = am.getHistoricalProcessExitReasons(null, 0, 32)

    exits.filter { it.timestamp > since && it.description?.contains("MemoryLimiter") == true }
        .sortedBy { it.timestamp }
        .forEach { log("app_exit_memory_limit", it.description.orEmpty().take(100)) }

    // Advance past every exit seen, kills or not, and never move backwards.
    val newest = exits.maxOfOrNull { it.timestamp } ?: since
    prefs.edit().putLong("watermark", maxOf(since, newest)).apply()
}
```

The watermark took the most thought. The history holds every recent process death, and nearly all of them are ordinary, like the user swiping the app away. If the watermark moved only on memory kills, an app that only ever got swiped away would re-scan and re-classify its whole history on every launch. Because it moves past every exit and never backwards, a platform that trims its history can't bring back an exit that was already reported.

The reason code is the generic `REASON_OTHER`, so the match is on the description text. The watermark sits in its own `SharedPreferences` file because this runs in `Application.onCreate`, before the dependency injection container exists. The read runs on `Dispatchers.IO` and nothing waits for it. It's a binder call at process start, and if it fails the app loses one diagnostic and still launches. Sixteen unit tests pin the classification, the watermark movement, history trimming and the 100-character cut.

The all-apps page, as I read it on October 31, also documents `adb shell am memory-limiter` for triggering the limiter by hand, with a `manual <pid> <limit>` mode and a `status` subcommand.

## Raising targetSdk with zero Android 17 users

With both changes fixed, I still had to decide when to raise `targetSdk`. Analytics over a 14-day window showed zero Android 17 users across all four apps. The newest version anyone ran was Android 16. None of the changes on either page reached anyone yet, so that week was the cheapest time to opt in.

Changing `targetSdk` in the repository doesn't reach a user by itself. I raised it to 37 and made the manual large-screen test pass a precondition for the next store deploy. I didn't want one manual step to hold the whole SDK upgrade for an open-ended stretch.

## Before and after the second audit

| | July 31 (targeting page only) | August 21 (both pages) |
|---|---|---|
| behavior changes reviewed | 15 | 15 + 9 |
| changes needing code in this app | 0 | 2 (both from the all-apps page) |
| `targetSdk` | 36 | 37 |
| lint issues | 1 (`OldTargetApi`) | 0 |
| host tests | 358 | 495, 0 failures |

The test count also grew from other work in those three weeks. The reporter costs one event definition and one binder call per launch.

## Two audits with two dates

The season premise had been copied into thirteen places before I looked at the monthly numbers behind it. Nobody re-checks a line like "wait until after the season" once it's in a decision record, me included.

The July audit was careful and answered what it asked: what changes when I raise `targetSdk`. It never asked what changes when users install the new OS. That question has its own page and no opt-out, so it reaches users first. I now run a platform migration as two audits, one per page, each with the date I read it, since both pages kept changing after release. I write down the all-apps table even when every row says "no". Nine rows of "no" show that I read the page.
