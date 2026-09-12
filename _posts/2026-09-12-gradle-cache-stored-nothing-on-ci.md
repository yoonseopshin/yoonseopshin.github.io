---
title: "setup-gradle v3 failed every cache call and my CI stayed green"
description: "An old setup-gradle logged each failed cache restore and save as a warning. The job stayed green with zero entries until I read the log and pinned v5."
date: 2026-09-12 13:46:53 +0900
categories: [Build & CI]
tags: [gradle, github-actions, build-cache, kotlin-multiplatform, ci]
lang: en
hidden: false
mermaid: false
ref: gradle-cache-stored-nothing-on-ci
permalink: /posts/gradle-cache-stored-nothing-on-ci/
math: false
---

I turned on the Gradle build cache for a Kotlin Multiplatform project on GitHub Actions, pushed, and got a green run. `gh cache list` showed zero Gradle entries. Every restore and every save had failed, and the action had logged each failure as a warning, so nothing in the run's status said so.

## Two jobs compiling the same Kotlin

The project is a Compose Multiplatform app (Android and iOS) in a private repository. Private repositories get a monthly allowance of free Actions minutes, and this project lived inside it, so runner-minutes were what I was trying to save. Wall-clock time mattered less.

The workflow ran on pushes to the default branch, with two build jobs on `ubuntu-latest`, and `build-android` waited for `test`. On the last green run before I changed anything, `test` took 10m39s and `build-android` took 13m47s. A large part of the second job went into compiling, on a fresh runner, the Kotlin the first job had just compiled on a runner that was then thrown away.

I made two changes in one commit:

1. I merged the two jobs, so the assemble step reuses the test step's outputs through Gradle's ordinary up-to-date checks. Locally, after a `clean`, the merged sequence ran the assemble with 253 of 334 tasks up-to-date.
2. I set `org.gradle.caching=true` so outputs could carry across runs as well as across steps on one runner. `gradle/actions/setup-gradle` already saved and restored Gradle User Home, which holds the local build cache directory (`caches/build-cache-1`). Since the workflow ran only on the default branch, the action would write entries rather than open the cache read-only. Locally, a clean build served 117 of 433 tasks from cache.

I didn't turn 117 of 433 into a CI estimate. A laptop has a warm daemon and downloaded dependencies, and a hosted runner has neither, so I planned to measure the first CI run instead.

Running the two jobs in parallel would have bought wall-clock time and no minutes. The free tier metered minutes, so I merged them.

## The Setup Gradle log on the first run

The first run after the change was green, and the merged build job took 15m25s. Part of that was a real win. Then I opened the log of the `Setup Gradle` step and its post step. The workflow was still on `setup-gradle@v3`, and the restore said:

```
Failed to restore gradle-home-v1|Linux|build[…]: Cache service responded with 400
```

Each save in the post step got GitHub's HTML error page ("Our services aren't available right now") back instead of a cache response. All of them were warnings, and the job concluded `success`. The cache list agreed:

```bash
gh cache list --key gradle-home
# no entries
```

I assumed a cache service outage. But other workflows in the same repository had written pip caches that same week, and those entries were in `gh cache list`, so the service was taking writes. This version of the action couldn't talk to it. v3 was three major versions behind, and its post step also printed a Node 20 deprecation warning.

The post step still spent about a minute per push trying to save and got nothing for it. The build stayed green the whole time, so nothing would have sent me to look.

## Pinning v5 while v6 was out

v6 was already out when I bumped the version, and I didn't take it. v6 moves caching into a separate proprietary component (`gradle-actions-caching`) with its own licence terms to accept. Those terms may well be fine. Agreeing to them is a different decision from fixing a bug, though, and I didn't want to make it as a side effect. v5 still has caching built in, so I pinned that:

```yaml
- name: Setup Gradle
  uses: gradle/actions/setup-gradle@v5
```

```properties
# gradle.properties
org.gradle.caching=true
```

The comment above the step says why v5 and why not v6, so whoever bumps it next reads the licence question before the changelog.

## What v5 restored

While writing this post I went back to the run logs with `gh run view <id> --log`. A version bump proves as little as turning the cache on did. The first two runs on v5 started from nothing, as expected:

```
Gradle User Home cache not found. Will initialize empty.
```

The third started after the first v5 run had finished saving, and it restored a real entry:

```
Cache hit for restore-key: gradle-home-v1|Linux-X64|build[…]-<sha>
Cache Size: ~101 MB (106283039 B)
Cache restored successfully
```

I took each build job's duration from `gh run view <id> --json jobs`, as `completedAt` minus `startedAt`:

| Runs | Setup | Build job duration |
|---|---|---|
| 1 | Two jobs, v3, no build cache | 10m39s + 13m47s, sequential |
| 1 | One job, v3, cache "on" but nothing stored | 15m25s |
| 2 | One job, v5, empty cache (first saves) | 16m56s, 17m21s |
| 100 | One job, v5, warm cache, 2026-09-12 to 09-23 | median 6m51s, range 3m02s to 15m16s |

Merging the jobs took about 24 minutes of sequential work down to 15m25s, and the cache contributed nothing to that. Once the cache worked, it took the merged job from 15 to 17 minutes down to a median under 7. Of the 100 warm runs, 26 finished in five minutes or less, 70 took five to ten, and 4 took longer than ten.

## A 1 MB cache hit

Three of those four slow runs went back to back one evening. Each restored a Gradle User Home entry of about 1 MB, where runs earlier that day had restored roughly 62 MB. Earlier that evening, three runs had failed within two minutes at a shell check, before any Gradle step ran, and the slow streak started right after the third. The first successful run after the streak restored about 102 MB and took 3m23s.

The log called every one of these a cache hit. A healthy entry that day weighed more than fifty times as much as the 1 MB one, and the run's status looked the same either way.

## Checking the entry and its size

A cache is optional by design, so setup-gradle is right to let the build continue when it can't reach the backend. That leaves the check to something outside the action. The project's CI doc now says a cache counts as on only once `gh cache list` shows its entries, and after the 1 MB evening I check the size too. Run after a default-branch build, this script turns a missing or tiny entry into a failed step:

```bash
#!/usr/bin/env bash
# Fail if the newest Gradle home cache entry is missing or suspiciously small.
set -euo pipefail
min_mb="${MIN_CACHE_MB:-20}"

size=$(gh cache list --key gradle-home --sort created_at --order desc --limit 1 \
         --json sizeInBytes --jq '.[0].sizeInBytes // 0')

if (( size < min_mb * 1024 * 1024 )); then
  echo "Gradle home cache missing or tiny: ${size} bytes" >&2
  exit 1
fi
echo "Gradle home cache: $(( size / 1024 / 1024 )) MB"
```

Pick the threshold from what a healthy entry weighs in your own logs. Mine ranged from about 62 MB to 102 MB.

I caught the v3 failure on the first run only because I was reading job durations and opened the cache step's log on the way. Before a change lands, I now write down the artifact that would show it worked, then go and look at that artifact instead of the status badge. For this cache it was the entry and its size. For the v5 pin it was the licence.

The minutes ran short eleven days later anyway, for a reason unrelated to the cache. I wrote that one up [separately](/posts/ci-minutes-paths-ignore-blocklist/).
