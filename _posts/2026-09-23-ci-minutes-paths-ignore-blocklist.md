---
title: "A three-entry paths-ignore list spent 77% of my CI minutes"
description: "A blocklist trigger ran an 8-minute Kotlin build on 34 of 40 commits. I measured the minutes and replayed an allowlist against git history first."
date: 2026-09-23 16:15:21 +0900
categories: [Build & CI]
tags: [github-actions, ci, monorepo, gradle, kotlin-multiplatform]
lang: en
hidden: false
mermaid: false
ref: ci-minutes-paths-ignore-blocklist
permalink: /posts/ci-minutes-paths-ignore-blocklist/
math: false
---

One GitHub Actions workflow accounted for 77% of my repository's projected monthly minutes. It ran an 8-minute Kotlin compile on 34 of the last 40 commits, and only 12 of those 40 had touched Kotlin or Gradle. I'd already made each run cheap. What cost the minutes was the trigger, a three-entry `paths-ignore` list.

## Runs that wouldn't start

The repository is private and holds a Kotlin Multiplatform app plus everything around it: Python tooling, agent skill files, a static site, marketing assets, an admin tool, Cloud Functions. Private repositories get a monthly allowance of free Actions minutes, 2,000 on this plan. On 2026-09-23 every run started to fail before its first step with this:

```
The job was not started because recent account payments have failed or your
spending limit needs to be increased.
```

The wording points at payments. Before touching any settings I wanted to know whether the allowance had run out, so I measured billed job-minutes over the previous five days, 2026-09-19 to 09-23, and projected them to a month. That came to about 2,129 minutes against the 2,000 allowance. One workflow, the Kotlin build-and-test, accounted for 1,644 of them, 77%. An exhausted allowance was the plausible reading, and it was obvious where to cut.

I'd already brought that workflow's run time down by merging jobs and getting the build cache to work, which is its [own post](/posts/gradle-cache-stored-nothing-on-ci/). A typical run took around 7 minutes. What was left to cut was the number of runs.

## 22 top-level entries in February, 51 in September

The trigger looked reasonable:

```yaml
on:
  push:
    branches: [ main ]
    paths-ignore:
      - 'functions/**'
      - 'docs/**'
      - '*.md'
```

Everything except Cloud Functions and documentation started a Kotlin build. I wrote that list in February, when I changed the trigger from a two-entry allowlist (the version catalog and the SQL schema directory) to "every push except these" so that CI ran on ordinary code changes. In February the repository had 22 top-level entries. By September it had 51, and most of the new ones had nothing to do with Kotlin: `tools/`, `.claude/skills/`, `site/`, `marketing/`, `admin/`, a `COPY.yaml` of app copy. Every one of them now started an 8-minute compile. Nobody had edited the list. The tree had grown around it.

To see how often that mattered, I replayed the last 40 commits against the filter. A small script read each commit's changed files from `git log --name-only` and matched them with GitHub's glob rules, where `*` stops at a slash and `**` crosses it:

| Trigger | Fires on the last 40 commits |
|---|---|
| `paths-ignore` (functions, docs, `*.md`) | 34 |
| Commits that touched Kotlin or Gradle | 12 |

28 of the 40 commits (70%) changed no Kotlin or Gradle, and most of them still paid for a build.

## Keeping the compile gate

Deleting the workflow would have saved the most minutes, and in September I decided against it. The project has no staging environment, and store releases run locally through Fastlane. Without a compile gate, I'd first find out about a Kotlin commit that didn't compile in the middle of a release. The workflow was there to catch that earlier, and for that it only had to run on commits that could break the build.

A second, much cheaper workflow (the harness check that enforces repository rules on a fresh clone) cost about a minute per run and 7% of the total. I left it alone.

## Deriving the allowlist from the steps

I inverted the filter, listing what should trigger a build instead of what shouldn't. That changes how a mistake costs you. If I forgot an entry in the old list, I paid for builds I didn't need. Forgetting one in an allowlist would let a real change skip the gate with no warning, which is worse, so I didn't guess the entries. I took them from what each step of the workflow reads.

Kotlin sources, Gradle scripts and the Gradle directories were obvious. The rest took reading the steps. The workflow decodes per-app config with a script in `tools/ci/`, reads the flavor list with a Python checker, and runs a shell script that checks the iOS dependency versions. That checker parses the Xcode build configuration files and every Swift file, and the shell script reads the Xcode project file. Nothing in the workflow compiles Swift, but a change in the iOS directory could still break a step, so it went on the list. The result, trimmed:

```yaml
on:
  push:
    branches: [ main ]
    paths:
      - '**/*.kt'
      - '**/*.kts'
      - '**/*.pro'
      - 'gradle/**'
      - 'gradle.properties'
      - 'gradlew'
      - 'app/**'            # each Gradle module directory, listed one by one
      - 'iosApp/**'         # read by the version and registry checks
      - 'tools/ci/**'       # scripts the steps call
      - 'tools/check-flavors.py'
      - 'scripts/verify-ios-versions.sh'
      - '.github/workflows/build.yml'
```

I also left a comment in the workflow saying that anything added to the steps belongs in this list too. Forgetting that edit is how an allowlist misses a change.

## Replaying the same 40 commits

Before merging, I ran the allowlist over the same 40 commits with the same script. The core of it is short enough to show:

```python
import re, subprocess

def glob_re(p):  # GitHub-style: '*' stays inside a segment, '**' crosses '/'
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i): out += "(?:.*/)?"; i += 3
        elif p.startswith("**", i): out += ".*"; i += 2
        elif p[i] == "*": out += "[^/]*"; i += 1
        else: out += re.escape(p[i]); i += 1
    return re.compile(f"^{out}$")

def commits(n=40, rev="HEAD"):  # one list of changed paths per commit
    log = subprocess.run(["git", "log", f"-{n}", "--format=%x1e", "--name-only", "--no-renames", rev],
                         capture_output=True, text=True, check=True).stdout
    return [[f for f in c.splitlines() if f] for c in log.split("\x1e")[1:]]

hit = lambda pats, f: any(re.match(p, f) for p in pats)
IGNORE = [glob_re(p) for p in ["functions/**", "docs/**", "*.md"]]
ALLOW = [glob_re(p) for p in ["**/*.kt", "**/*.kts", "gradle/**", "app/**", "iosApp/**"]]
KOTLIN = [glob_re(p) for p in ["**/*.kt", "**/*.kts", "gradle/**"]]

cs = commits()
print("paths-ignore fires:", sum(any(not hit(IGNORE, f) for f in c) for c in cs))
print("allowlist fires:  ", sum(any(hit(ALLOW, f) for f in c) for c in cs))
print("missed Kotlin:    ", sum(any(hit(KOTLIN, f) for f in c) and not any(hit(ALLOW, f) for f in c) for c in cs))
```

With the full allowlist in `ALLOW` and `rev` set to the commit before the change, it prints:

```
paths-ignore fires: 34
allowlist fires:   14
missed Kotlin:     0
```

The script handles only `*` and `**`, which was all either filter used. It also judges commit by commit, while GitHub judges a push, so a push of several commits is matched on their combined diff.

| Trigger | Fires on the last 40 commits | Kotlin/Gradle commits missed |
|---|---|---|
| `paths-ignore` | 34 | 0 |
| `paths` allowlist | 14 | 0 |

That's 59% fewer runs with no false negatives on this sample. Scaling the workflow's minutes by the same ratio, 1,644 × 14 / 34 is about 680 minutes a month, which puts the repository at about 1,160 against the 2,000 allowance.

## 84 runs for 272 commits, then no workflow

The allowlist shipped on 2026-09-23. Runs resumed on 2026-10-05, and from then until the morning of 10-13 the default branch took 272 commits while the workflow ran 84 times, about 31%. That's pushes against commits, so it's a rough comparison, but it's in line with the 35% (14 of 40) from the replay.

The other half of the bill is how many commits there are, and that went up: 326 commits in the first 23 days of September, 272 in the eight and a half days after runs resumed. On 2026-10-13 I removed the workflow after all. By then the same checks ran locally before each commit and again before each release, and the release lanes compiled every app for real. The CI verdict arrived after the binaries were already in the stores, so it no longer stopped anything. In September I'd kept the workflow so that a broken commit wouldn't first show up mid-release, and the local gates now covered that. The one cheap check that existed only in that workflow, the iOS dependency-version script, moved into the small harness workflow, and I added its inputs to that workflow's path filter.

## Changing a path filter now

I replay a new filter against recent history with the script above, and I count missed Kotlin commits before I count saved runs. 34 → 14 with zero misses is what let me merge this one. I also stopped treating a blocklist trigger as finished once it's written. This one was correct in February, nobody touched it until September, and every new top-level directory made it cost more.
