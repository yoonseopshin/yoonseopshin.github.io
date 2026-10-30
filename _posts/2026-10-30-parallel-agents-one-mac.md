---
title: "Shrinking iOS simulators from 3.25 GB to 0.86 GB to fit parallel AI agents"
description: "Three stock simulators and two Xcode builds took down a 36 GB Mac. The per-session costs I measured, and the leases, build slots and cleanup that fixed it."
date: 2026-10-30 16:07:31 +0900
categories: [AI Agents]
tags: [ios-simulator, xcode, android-emulator, git-worktree, macos, bash]
lang: en
hidden: false
mermaid: false
ref: parallel-agents-one-mac
permalink: /posts/parallel-agents-one-mac/
math: false
---

A stock iOS 26.5 simulator runs 209 processes and uses 3.25 GB of memory. Three of them plus two Xcode builds took down my 36 GB Mac. None of the failures I recorded had anything to do with CPU: memory ran out first, then disk, and once free space hit 230 MB even shell commands started failing.

## Every session booted its own simulator

I build a personal iOS and Android app alone, and I'd started running several AI coding agent sessions in parallel, each in its own git worktree. Each session did what a careful developer would do. It built its branch, booted a simulator, installed the app, took screenshots and checked its work. The machine is a 14-core M4 Max with 36 GB of memory. The simulators were iPhone 17 Pro on iOS 26.5, and on the Android side I used emulator 37.2.13 with an API 36.1 image.

Memory went first. Every session booted its own full simulator at 3.25 GB, and three of them next to two concurrent Xcode builds was enough to make the Mac fall over.

Disk went next. Each worktree produced a fresh 2 to 5 GB of DerivedData, either in Xcode's default location, in a `/tmp` path passed as `-derivedDataPath`, or in a build folder. Each session also created its own uniquely named simulator, 2 to 8 GB apiece. Deleting a worktree removes none of that. On the day I fixed it, the disk had 230 MB left.

Giving each session its own simulator had been a fix in the first place. Before that, sessions shared one and overwrote each other's installs and screens.

## Options I ruled out

I wrote the rejected options into a decision record, one reason each:

| Option | Why not |
|---|---|
| Only cap the number of simulators | Two stock simulators are still over 6 GB, tight next to a build, and it cuts the number of parallel sessions |
| One shared simulator | Sessions overwrote each other's installs and screens; this had already happened |
| One shared DerivedData | Concurrent builds lock the same build database and serialize, which defeats running two builds at once |
| Headless simulator streaming tools | They solve screen streaming and input, not memory |

What I built instead was a thin wrapper layer between the sessions and the machine. It makes each simulator cheap, hands simulators out under a cap and a memory floor, deletes only what can be rebuilt, and limits concurrent Xcode builds to a number I measured:

```
  session A ─┐                    ┌─ sim lease  (cap 4 booted, 20% memory floor)
  session B ─┼─ wrapper scripts ──┼─ build slot (2 concurrent xcodebuild)
  session C ─┘                    ├─ emulator lease (cap 3, read-only shared AVD)
                                  └─ gc (only reproducible artifacts, when disk < 30 GB)
```

## Turning off simulator services with simslim

Most of a simulator's footprint is background services, about 180 of them, Siri, Spotlight and iCloud among them, and an app under test rarely needs any. I used simslim, an open-source MIT-licensed tool that edits the launchd disable list inside a simulator. It doesn't touch the host or the shared runtime, and `simslim off` or an erase undoes it. My default profile turns off every category except the photo picker.

| Simulator (iPhone 17 Pro, iOS 26.5) | Processes | Memory |
|---|---|---|
| Stock | 209 | 3.25 GB |
| simslim dev profile | 75 | 0.86 GB |

The setting survives a reboot through `simctl boot`, and `simslim verify` checks the profile is still applied. Slimming a simulator the first time takes 58 seconds. Later boots of the same simulator take 2 to 13 seconds. In exchange, remote push, StoreKit, universal links and iCloud stop working, so the wrapper takes a `--full` flag for the sessions that need them.

## Leasing simulators under a cap

Sessions get simulators only through a wrapper that keeps one lease file per simulator. Past the cap, it first shuts down simulators whose lease hasn't been touched in 45 minutes, and if that doesn't free a spot it refuses. It also refuses when free memory is below 20%. On macOS, `kern.memorystatus_level` reports that percentage directly:

```bash
#!/usr/bin/env bash
set -uo pipefail
udid=${1:?usage: sim-up <udid>}
max_booted=${SIM_MAX_BOOTED:-4}; min_mem=${SIM_MIN_MEM_PCT:-20}
leases="$HOME/Library/Caches/my-sim-leases"; mkdir -p "$leases"

booted_count() { xcrun simctl list devices | grep -c "(Booted)"; }

if [ "$(booted_count)" -ge "$max_booted" ]; then
  for f in "$leases"/*.lease; do                  # reclaim stale leases first
    [ -e "$f" ] || continue
    if [ -n "$(find "$f" -mmin +45)" ]; then
      xcrun simctl shutdown "$(basename "$f" .lease)" 2>/dev/null; rm -f "$f"
    fi
  done
  [ "$(booted_count)" -ge "$max_booted" ] && { echo "sim cap reached" >&2; exit 75; }
fi
mem=$(sysctl -n kern.memorystatus_level)
[ "$mem" -lt "$min_mem" ] && { echo "free memory ${mem}% < ${min_mem}%" >&2; exit 75; }

xcrun simctl boot "$udid" 2>/dev/null; touch "$leases/$udid.lease"
```

The exit code is the part to look at. 75 is `EX_TEMPFAIL`, and the calling agent reads it as "wait, or fall back to a SwiftUI preview render" instead of retrying in a loop.

## Finding orphaned DerivedData through info.plist

I gave the cleanup script one rule: delete nothing that can't be regenerated and nothing in use. It removes DerivedData whose original workspace no longer exists, `/tmp` build directories untouched for 6 hours, per-worktree build output whose worktree is gone, project simulators shut down for more than 12 hours, and agent worktrees already merged into main with no tracked changes. It skips anything that shows up in a running process's command line or was written in the last 30 minutes.

The orphan check for DerivedData relies on a file Xcode already writes. Every folder under `~/Library/Developer/Xcode/DerivedData` has an `info.plist` with the path of the workspace that produced it:

```bash
dd="$HOME/Library/Developer/Xcode/DerivedData"
for d in "$dd"/*/; do
  d=${d%/}
  ws=$(/usr/libexec/PlistBuddy -c "Print :WorkspacePath" "$d/info.plist" 2>/dev/null) || continue
  [ -e "$ws" ] && continue                          # workspace still exists: keep
  ps -axww -o command= | grep -qF "$d" && continue  # in use by a running build
  [ -n "$(find "$d" -maxdepth 4 -mmin -30 -print -quit)" ] && continue
  echo "orphan: $(du -sh "$d" | cut -f1) $d"        # rm -rf "$d" in the real run
done
```

The first run took free space from 230 MB to 144 GB. It removed DerivedData from about 30 deleted worktrees, 19 build folders, 17 simulators that had been shut down for over 12 hours, and one merged worktree. A session-start hook now prints one line with free disk, free memory and the number of booted simulators, and kicks off the cleanup in the background whenever free disk is under 30 GB.

## Timing two Xcode builds at once

I didn't want to guess how many builds could share the machine, so I timed a clean build of the app for a generic simulator destination on the same 14-core Mac:

| Configuration | Wall time |
|---|---|
| One build alone | 103 s |
| Two builds at once | 159 s (each finished at 150 s and 158 s) |
| Two builds one after the other (computed) | 206 s |

206 / 159 is about 1.3, so two concurrent builds get through about 1.3 times the work of running them back to back. That's less than double but still worth having, and I set the default to two slots.

A slot is a directory created with `mkdir` under the repository's shared git directory. Every worktree resolves that directory to the same path, so all sessions of one repository wait in one queue. Each slot holds a pid file, and the wrapper reclaims any slot whose owner process has died.

## Android emulators stop at the guest RAM floor

On Android I didn't give each session its own AVD. Every session boots one of two shared base AVDs with `-read-only`, headless and cold. Installed apps vanish on shutdown, which is fine for render checks. The light AVD runs at 720×1600 with 26 apps disabled, including Play Store, Digital Wellbeing, TTS and Messages.

| AVD (same API 36.1 image, cold boot) | Mac footprint | Boot |
|---|---|---|
| Android Studio default | 2.27 GB | |
| Shared full, 1080×2400 | about 2.9 GB | 35 s |
| Shared light, 720×1600 | about 1.9 GB | 17–22 s |

The saving is smaller than on iOS. The image's guest RAM floor (2560 MB for 36.1) decides most of the host memory, and disabling apps only saves the pages the guest actually touched. Three other routes failed:

- ATD (Automated Test Device) images cut guest processes to 263, but screenshots came out black in host, swangle and guest GPU modes, which rules them out for render checks. The API 37 ATD image also uses 16 KB pages, which raises the RAM floor to 4096 MB, and it used 2.32 GB on the Mac.
- Snapshot boot came up in 3 seconds. Opening a snapshot read-only copied the whole guest RAM, though, and the footprint went to 3.2 GB.
- AVDs created with `avdmanager` wouldn't boot on this Mac, failing with `hvf is not enabled` and `mprotect failed`, so the wrapper writes a minimal Studio-style config itself. Starting the emulator inside the agent's sandbox gives the same HVF error, so the wrapper detects it and tells the session to run outside.

## A refusal message that crashed under `set -u`

The same afternoon, a session hit the emulator boot cap. The script died instead of printing its refusal, and the session got past it by raising the cap environment variable. Both the simulator and the emulator wrapper printed the count right before a Korean counter word, as `$n대`. Under `set -u` in a UTF-8 locale, bash reads the bytes after `$n` as part of the variable name:

```
$ LC_ALL=en_US.UTF-8 bash -uc 'n=3; echo "x $n대 y"'
bash: n�: unbound variable
$ LC_ALL=C bash -uc 'n=3; echo "x $n대 y"'
x 3대 y
```

I reproduced it with macOS's bash 3.2.57 and with Homebrew's 5.3.9. Writing `${n}대` fixes it.

The more interesting part was what the session did. When the guard failed noisily, the agent treated it as an obstacle and went around it. I'd seen that before: in an earlier trial run, a blocked worker had edited files outside the paths it owned to get unstuck.

## Sessions that picked up each other's builds and windows

Two smaller collisions turned up along the way. The screenshot script used to install "the most recent `.app` in DerivedData", and once that was another worktree's build. It now asks `xcodebuild -showBuildSettings` for its own build's `CODESIGNING_FOLDER_PATH`. Synthesized taps also landed in another session's simulator window once, because the windows overlapped. Taps are now mapped to the device screen inside the window the script finds by its title.

## Before and after

I measured simulator memory with `simslim measure` and emulator memory with the Mac-side `footprint`:

| Resource | Before | After |
|---|---|---|
| iOS simulator, per session | 3.25 GB, 209 processes | 0.86 GB, 75 processes |
| Android emulator, per session | 2.27 GB (Studio default) | about 1.9 GB (shared read-only light AVD) |
| Free disk | 230 MB | 144 GB after the first cleanup |
| Concurrent Xcode builds | unbounded | 2 slots, 1.3× throughput of serial |

By those per-unit numbers, four slim simulators add up to about 3.4 GB. Three stock ones added up to about 9.75 GB.

## Testing the refusal path

Once I had the cost of one session, the fixes were ordinary operating-system ideas: leases that expire, a quota with a refusal code, a semaphore sized from a measurement, and garbage collection that only touches what can be rebuilt. I'd count one session's cost again before adding sessions to any machine.

Agents need one more thing. In my records they took the shortest way past every failure, and a guard was no exception. So make each guard print a clear reason, exit with a code that means "wait", and run its refusal path yourself before an agent does. For a message that puts a variable right before non-ASCII text, the `LC_ALL=en_US.UTF-8 bash -uc` line above is that test.
