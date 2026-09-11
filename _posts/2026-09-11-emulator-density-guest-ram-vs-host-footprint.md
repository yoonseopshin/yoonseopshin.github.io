---
title: "A 4 GB Android emulator uses 4.8 GB of host RAM"
description: "On 8-core, 12 GB hosts with no GPU, a 4096 MB emulator took 4.6 to 5.5 GB. Why my capacity gate approved two per host, and how I fixed it."
date: 2026-09-11 14:54:19 +0900
categories: [Build & CI]
tags: [android-emulator, capacity-planning, linux, oom, testing]
lang: en
hidden: false
mermaid: false
ref: emulator-density-guest-ram-vs-host-footprint
permalink: /posts/emulator-density-guest-ram-vs-host-footprint/
math: false
---

On my hosts, an Android emulator started with `-memory 4096` held between 4,605 and 5,457 MB of resident memory, with a median of 4,802 MB. I'd planned capacity on the 4096. I first put two emulators on each host, and after I measured that gap I went back to one.

## Twelve VMs, no GPU

The test farm was twelve Linux VMs, each with 8 cores and about 12 GB of RAM (`free -m` reports 11,959 MB total), and no GPU. Each VM ran one Android emulator: an API 34 x86_64 image, headless, started with `-gpu software -memory 4096 -cores 3`.

I wanted more parallel test slots from the same twelve machines. How many emulators could one host run before tests got worse? Three cores each on an 8-core box suggests two, and four gigabytes each on a 12 GB box gives two, maybe three.

## Trying three and four per host

I started with the direct experiment. Some hosts got two emulators, some three, some four, all at 4096 MB and 3 cores.

The four-emulator hosts fell over quickly. One sat at 11,477 of 11,959 MB used with a load average of 10.7, and one of its four qemu processes was already gone. Another hit the OOM killer and its load climbed to 58. SSH timed out during the banner exchange, before authentication, so I couldn't even log in to look.

Next I shrank each emulator to fit: 3072 MB and 2 cores at density three, 2560 MB and 2 cores at density four. That run told me nothing. The restart handler in my own health check sent SIGTERM asynchronously, so applying the change stopped every instance on those hosts and there was never a steady state to measure. Until I fixed that handler, no density experiment could give me valid data.

One configuration had been seen working: two emulators at 4096 MB and 3 cores, on one host, with both instances reporting healthy. I set nine hosts to two emulators and kept three at one, and slots went from 12 to 21. That answer rested on a health check at idle.

## Rules fixed before the run

A few days later I wrote the experiment down properly. Both instances being healthy didn't tell me whether tests got worse.

First, a static gate that rejects a density before any emulator starts:

- total emulator memory at most 75% of host memory
- at least 2 GB of host memory left over
- total emulator cores at most host cores minus one

Then a read-only probe that samples every emulator on the same schema: ADB round-trip latency, health status, qemu CPU and RSS, host load, CPU and memory pressure (PSI), swap, OOM counter, ANR count, and test pass counts when a test is running. It never starts, stops, or kills anything.

And a report whose decision rules I fixed in advance. Density two fails against density one if test success drops by 2 percentage points or more, if p95 latency rises by 50% or more, if any OOM happens, or if memory pressure stays over threshold. A run with no real test traffic gets the label `idle-soak` and is never reported as a pass.

Density three was out before it started, since 3 x 3 cores is 9 and the gate allows 7. That left two against one.

## 700 MB free with two emulators

For a density-one control, I moved three of the density-two hosts back to one emulator. My note in the inventory gave the reason: with two emulators running, a host's available memory dropped to around 700 MB, and a host in that state was no fair stand-in for one emulator with room to spare.

That didn't add up. Two emulators at 4096 MB is 8,192 MB, and 11,959 − 8,192 leaves about 3.7 GB, not 700 MB. Something on the host was using memory the plan didn't count.

## Measuring qemu RSS on all twelve hosts

The next day I measured the resident size of every emulator's qemu process across all twelve hosts. For a guest configured with 4096 MB:

| | host RSS per emulator |
|---|---|
| minimum | 4,605 MB |
| median | 4,802 MB |
| maximum | 5,457 MB |

Two of those on one host used 81% to 89% of host memory while idle. Under load, those hosts died to a global OOM.

The extra memory comes from two places. qemu has its own overhead on top of guest RAM. And with `-gpu software` the emulator renders on the CPU, so the framebuffer and color buffers that would sit on a GPU take host RAM instead. With no GPU, there's no way around it.

## Counting host footprint in the gate

My gate had approved density two because it multiplied guest RAM by N. I changed it to judge by host footprint, guest RAM plus a per-emulator overhead that defaults to 1024 MB, and to print both numbers so a verdict shows its reasons. Rewritten with generic names, the check is:

```bash
#!/bin/bash
# usage: gate.sh HOST_MB HOST_CORES N GUEST_MB GUEST_CORES
host_mb=$1 host_cores=$2 n=$3 guest_mb=$4 guest_cores=$5
overhead_mb=${EMU_OVERHEAD_MB:-1024}   # qemu + software GPU buffers

per_emu_mb=$((guest_mb + overhead_mb))
need_mb=$((n * per_emu_mb))
reasons=""
reject() { reasons="${reasons:+$reasons,}\"$1\""; }

(( need_mb <= host_mb * 75 / 100 ))     || reject memory_budget
(( host_mb - need_mb >= 2048 ))         || reject memory_headroom
(( n * guest_cores <= host_cores - 1 )) || reject core_budget

echo "{\"n\":$n,\"per_emu_mb\":$per_emu_mb,\"need_mb\":$need_mb,\"reasons\":[$reasons]}"
[ -z "$reasons" ]
```

With these hosts' numbers, once with the default overhead and once with it set to zero:

```console
$ ./gate.sh 11959 8 2 4096 3; echo "exit=$?"
{"n":2,"per_emu_mb":5120,"need_mb":10240,"reasons":["memory_budget","memory_headroom"]}
exit=1
$ EMU_OVERHEAD_MB=0 ./gate.sh 11959 8 2 4096 3; echo "exit=$?"
{"n":2,"per_emu_mb":4096,"need_mb":8192,"reasons":[]}
exit=0
```

Across N = 1 to 3, the old and new verdicts differ in one row:

| N | guest RAM only: need / headroom | verdict | with 1024 MB overhead: need / headroom | verdict |
|---|---|---|---|---|
| 1 | 4,096 / 7,863 MB | pass | 5,120 / 6,839 MB | pass |
| 2 | 8,192 / 3,767 MB | pass | 10,240 / 1,719 MB | memory budget, headroom |
| 3 | 12,288 / -329 MB | memory, headroom, cores | 15,360 / -3,401 MB | memory, headroom, cores |

The 75% budget on 11,959 MB is 8,969 MB, so 8,192 passed and 10,240 doesn't. The real gate's output for N=2, trimmed to the relevant fields:

```json
{"eligible":false,"n":2,"avd_memory_mb":4096,"avd_memory_overhead_mb":1024,
 "avd_effective_memory_mb":5120,"memory_required_mb":10240,
 "memory_headroom_mb":1719,"reasons":["memory_budget","memory_headroom"]}
```

I kept a test that sets the overhead to zero and checks that the gate reproduces the old verdict.

The 1024 MB default covers the median overhead I measured (4,802 − 4,096 = 706 MB) but not the worst one (5,457 − 4,096 = 1,361 MB). The 75% cap and the 2 GB headroom rule absorb the tail, as I read the gate. I could have set the default closer to the worst case.

Under the new gate, density two on these hosts isn't eligible. Every host went back to one emulator.

## Group labels came from the plan

The experiment tooling had one more bug: it would have compared the wrong groups. It assigned hosts to "density one" and "density two" by hostname range, hard-coded from the original plan. Once I retired the second emulator on the nine treatment hosts, they were all at density one, but the manifest would still have called them density two. The report would have claimed one against two after comparing one against one.

I changed the tooling to derive each host's group from the emulator count in its inventory entry and record that per-host density in the manifest. It now refuses densities above two instead of passing them through, and it takes an explicit exclude list. Two hosts went on that list, because the app under test crashed in the software renderer there. The resulting manifest has ten hosts at density one, none at density two, and two excluded. With an empty treatment group, the report withholds a verdict as `missing_control_or_treatment`.

## Back to one per host

| step | answer | based on |
|---|---|---|
| density 3 and 4 at 4096 MB | no | OOM, load 58, SSH unreachable |
| shrunken density 3 and 4 | no data | restart handler stopped all instances |
| density 2 at 4096 MB | yes, 21 slots | one host, both instances healthy at idle |
| density 2 with measured footprint | no, back to 12 slots | RSS 4,605 to 5,457 MB per emulator; 81 to 89% of host memory at idle |

The farm stayed at one emulator per host. Two per host would take either more memory per VM or less per emulator, and the gate checks either change before anything starts.

## Checking RSS before a density test

Now I measure the footprint first. On a host running a single emulator, one `ps -o rss` per qemu process would have shown a "4 GB" emulator using 4.6 to 5.5 GB before I ran any density experiment, and it takes a minute. With CPU rendering, `-memory` and RSS were far enough apart to change the answer.

The group-label bug worries me more. I now build experiment groups from the emulator count each host reports, and the report refuses to conclude when a group is empty.
