---
title: "A Compose dialog logged 144 impressions for 118 taps on its only button"
description: "The paywall impression was logged in the composable body, so recompositions logged it again. A LaunchedEffect keyed on the dialog's flag fixed it."
date: 2026-04-12 13:05:38 +0900
categories: [Android]
tags: [compose, analytics, recomposition, bigquery, firebase]
lang: en
hidden: false
mermaid: false
ref: compose-analytics-double-count
permalink: /posts/compose-analytics-double-count/
math: false
---

The analytics export showed 118 taps on my premium banner and 144 paywall impressions, and on the home screen that banner is the only way to open the paywall dialog. A funnel step was bigger than the step before it. The unique user counts for the two events matched, so the same people were being counted more than once. The cause was one logging call in the wrong place in a composable.

## Three events from banner to purchase

The app is a Compose Multiplatform quiz app with an optional one-time purchase. One code base ships as several quiz apps through product flavors, four of them by July. The purchase path from the home screen is three events in a row, logged through Firebase Analytics and read back from the BigQuery export:

```
iap_banner_click  ->  paywall_shown  ->  iap_purchase_click  ->  iap_purchase_success
   (tap banner)       (dialog opens)      (tap buy)               (store confirms)
```

The settings screen has the same banner and the same dialog with `referer = "settings"`. A third path, unlocking an explanation, goes straight to the store and skips the dialog.

Between the first two steps there's no branching. A banner click sets a flag, and the flag shows the dialog. Both events are logged on the home screen, and the click handler that logs `iap_banner_click` is the only place that sets the flag. So `banner_click` and `paywall_shown` should be equal.

## 26 extra impressions from the same users

For the home referer the export said:

| event | count | relationship |
|---|---|---|
| `iap_banner_click` | 118 | |
| `paywall_shown` | 144 | 26 more than the clicks, +22% |
| unique users, both events | equal | same people |

A step that's 22% larger than its only entry point means the second event fires more than once per open. If the extra events had come from different people, the unique user counts would have differed. They didn't, so I wasn't looking for an unknown second path into the dialog. The same users were logging the impression repeatedly.

## logEvent in the composable body

The impression was logged inside the `if` that shows the dialog, directly in the composable body:

```kotlin
var showPaywall by rememberSaveable { mutableStateOf(false) }

if (showPaywall) {
    analytics.logEvent("paywall_shown", mapOf("referer" to "home"))  // runs on every recomposition
    PaywallDialog(
        onDismiss = { showPaywall = false },
        onPurchase = { /* ... */ },
    )
}
```

Compose runs a composable body whenever it recomposes that part of the tree, and that can happen many times while the dialog is on screen. While the dialog was open, any change to state that composable read made the body run again. The `if` was still true, so `logEvent` ran again. Compose makes no promise about how many times that happens, so I didn't expect the excess to come out at a round 2x.

The settings screen had the same pattern with its own flag, so I fixed both.

## Moving the log into LaunchedEffect

The impression is a side effect of the dialog opening, so it belongs in an effect keyed to the thing that opens it:

```kotlin
LaunchedEffect(showPaywall) {
    if (showPaywall) {
        analytics.logEvent("paywall_shown", mapOf("referer" to "home"))
    }
}

if (showPaywall) {
    PaywallDialog(
        onDismiss = {
            analytics.logEvent("paywall_dismissed", mapOf("referer" to "home"))
            showPaywall = false
        },
        onPurchase = { /* ... */ },
    )
}
```

`LaunchedEffect` runs its block when it enters composition and again only when its key changes. Recomposing with `showPaywall == true` leaves the key alone, so nothing is logged. Flipping the flag from `false` to `true` restarts the effect and logs once. The `paywall_dismissed` and `iap_purchase_click` calls were already in click lambdas, which run once per tap, so the bug never touched them.

There's one case where this still logs twice, and I accepted it. The flag lives in `rememberSaveable`, so if the activity is recreated while the dialog is open, the flag comes back `true`, the effect enters composition again, and it logs a second impression. That's one extra event per recreation instead of one per recomposition. The user does see the dialog appear again, so I can argue it's a real second impression. If I wanted strict once-per-open, I'd move the "already logged" bit into saved state next to the flag.

## Splitting the funnel by entry point

In the same commit I changed how I read the funnel. Home, settings and explanation-unlock convert differently, and the last one never passes through the dialog. Blended into one funnel, they can't tell you which path a number belongs to. The report query now groups by the `referer` parameter:

```sql
SELECT
  event_name,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'referer') AS referer,
  COUNT(*) AS events,
  COUNT(DISTINCT user_pseudo_id) AS users
FROM `my-project.analytics_XXXX.events_*`
WHERE _TABLE_SUFFIX BETWEEN
    FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE('Asia/Seoul'), INTERVAL 30 DAY))
    AND FORMAT_DATE('%Y%m%d', CURRENT_DATE('Asia/Seoul'))
  AND event_name IN ('iap_banner_click', 'paywall_shown', 'paywall_dismissed',
                     'iap_purchase_click', 'iap_purchase_success')
GROUP BY event_name, referer
ORDER BY referer, event_name
```

Putting raw counts next to distinct users showed me the repeats, so the query keeps both columns for every event.

The split caused a different mistake in July. One report got its total by adding up the per-group `COUNT(DISTINCT user_pseudo_id)` values, and since the same user appears under several referer and error-type groups, the sum overstated how many people were involved. One figure dropped from 4 users to 2 when I re-ran it ungrouped. I wrote down a rule then: totals come from a separate query without the `GROUP BY`, never from adding up groups.

## 1 : 1 in every app by July

| measurement | `banner_click` : `paywall_shown` |
|---|---|
| before the fix, home referer (April) | 118 : 144 |
| after the fix, 30-day window (July, four apps) | 1 : 1 in every app |

The July check was part of a routine funnel review over a 30-day BigQuery window. I concluded that the two events are structurally the same step and took that edge of the funnel off the list of bottleneck candidates. While the impression count was inflated, the click-to-impression step had looked like a place worth digging into, so taking it off the list was the useful outcome.

## A check for a step with one way in

In Compose I now put anything that should happen once per appearance in an effect keyed on whatever describes the appearance, and keep the composable body to what's on screen. Logging made this mistake easy to miss because nothing visible went wrong: the UI didn't change, and the wrong number looked plausible on its own.

What caught it was a funnel step larger than its only entry point, with a distinct-user column next to the raw count. I'd add that check to any funnel on purpose: when step N can only be reached from step N-1, assert that N isn't bigger, and look at events per user whenever it is.
