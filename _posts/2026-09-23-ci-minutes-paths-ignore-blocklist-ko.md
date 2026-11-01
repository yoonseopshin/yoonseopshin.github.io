---
title: "GitHub Actions paths 필터로 CI 시간 줄이기"
description: "코틀린 빌드 워크플로우 하나가 월 예상 Actions 사용 시간의 77%를 썼다. 항목 셋짜리 paths-ignore가 최근 커밋 40개 중 34개에서 8분짜리 빌드를 띄운 것이 원인이었다."
date: 2026-09-23 16:15:21 +0900
categories: [Build & CI]
tags: [github-actions, ci, monorepo, gradle, kotlin-multiplatform]
lang: ko-KR
hidden: true
mermaid: false
ref: ci-minutes-paths-ignore-blocklist
permalink: /ko/posts/ci-minutes-paths-ignore-blocklist/
math: false
---

GitHub Actions 워크플로우 하나가 저장소의 월간 예상 사용 시간 중 77%를 쓰고 있었다. 최근 커밋 40개 중 34개에서 8분짜리 코틀린 컴파일이 돌았는데, 그 40개 중 코틀린이나 Gradle을 건드린 커밋은 12개뿐이었다. 빌드 한 번에 드는 시간은 이미 줄여 둔 뒤였으므로 문제는 항목 셋짜리 `paths-ignore` 트리거였다.

## 시작도 못 하고 실패한 실행

저장소는 비공개이고 Kotlin Multiplatform 앱과 그 주변 도구가 전부 들어 있다. 파이썬 도구, 에이전트 스킬 파일, 정적 사이트, 마케팅 자료, 어드민 도구, Cloud Functions까지 있다. 비공개 저장소에는 Actions 무료 사용 시간이 매달 정해져 있는데 이 요금제에서는 2,000분이다. 2026-09-23부터 모든 실행이 첫 단계에 들어가기도 전에 다음 메시지를 남기고 실패했다.

```
The job was not started because recent account payments have failed or your
spending limit needs to be increased.
```

문구만 보면 결제 문제다. 하지만 설정을 건드리기 전에 무료 한도를 다 쓴 것인지부터 알고 싶어서 2026-09-19부터 09-23까지 닷새 동안 과금된 job 사용 시간을 재고 한 달 치로 늘려 봤다. 2,000분 한도에 약 2,129분이 나왔고, 그중 1,644분(77%)이 코틀린 빌드·테스트 워크플로우 하나에서 나왔다. 한도를 다 쓴 것으로 보는 게 자연스러웠고 어디를 줄일지도 분명했다.

이 워크플로우는 job을 합치고 빌드 캐시가 제대로 돌게 해서 실행 시간을 이미 줄여 둔 상태였다. 그 과정은 [Gradle 캐시 글](/ko/posts/gradle-cache-stored-nothing-on-ci/)에 썼다. 한 번 도는 데 보통 7분 안팎이었으므로 줄일 곳은 실행 횟수였다.

## 2월 22개에서 9월 51개로 늘어난 최상위 항목

트리거는 그럴듯해 보였다.

```yaml
on:
  push:
    branches: [ main ]
    paths-ignore:
      - 'functions/**'
      - 'docs/**'
      - '*.md'
```

Cloud Functions와 문서를 뺀 나머지 변경에서는 전부 코틀린 빌드가 돌았다. 이 목록은 2월에 내가 썼다. 원래는 버전 카탈로그와 SQL 스키마 디렉토리만 보던 항목 둘짜리 허용 목록이었는데, 일반 코드 변경에도 CI가 돌게 하려고 "이것만 빼고 모든 푸시"로 바꾸면서 생긴 목록이다. 2월에 저장소 최상위 항목은 22개였다. 9월에는 51개가 됐고 새로 생긴 항목은 대부분 코틀린과 상관이 없었다. `tools/`, `.claude/skills/`, `site/`, `marketing/`, `admin/`, 앱 문구를 모은 `COPY.yaml` 같은 것들이다. 이 중 어디를 바꾸든 8분짜리 컴파일이 돌았다. 목록은 아무도 고치지 않았는데 저장소 트리만 커진 것이다.

얼마나 자주 그랬는지 보려고 최근 커밋 40개를 필터에 다시 돌려 봤다. 작은 스크립트로 `git log --name-only`에서 커밋마다 바뀐 파일을 읽고 GitHub의 glob 규칙으로 맞춰 봤는데, 이 규칙에서 `*`는 슬래시를 넘지 않고 `**`는 넘는다.

| 트리거 | 최근 커밋 40개 중 실행 |
|---|---|
| `paths-ignore` (functions, docs, `*.md`) | 34 |
| 코틀린이나 Gradle을 건드린 커밋 | 12 |

40개 중 28개(70%)는 코틀린도 Gradle도 바꾸지 않았는데 그 대부분에서 빌드가 돌았다.

## 컴파일 체크를 남긴 이유

워크플로우를 지우면 사용 시간을 가장 많이 아낄 수 있지만 9월에는 그러지 않기로 했다. 이 프로젝트에는 스테이징 환경이 없고 스토어 배포는 로컬에서 fastlane으로 한다. 컴파일 체크가 없으면 컴파일이 안 되는 코틀린 커밋을 배포 도중에야 알게 된다. 이 워크플로우는 그런 커밋을 더 일찍 잡으려고 만든 것이고, 그러려면 빌드를 깨뜨릴 수 있는 커밋에서만 돌면 충분했다.

훨씬 가벼운 워크플로우도 하나 있었다. 새로 클론한 저장소에서 저장소 규칙을 지키는지 보는 하네스 검사인데, 한 번 도는 데 1분쯤 들었고 전체의 7%였다. 이것은 그대로 뒀다.

## 단계가 읽는 파일로 만든 허용 목록

필터를 뒤집어서 빌드를 띄우지 않을 경로 대신 띄울 경로를 적었다. 그러면 실수했을 때의 손해가 달라진다. 예전 목록에서 항목을 빠뜨리면 필요 없는 빌드가 돌 뿐이지만, 허용 목록에서 빠뜨리면 실제 변경이 아무 경고 없이 컴파일 체크를 건너뛴다. 이쪽이 더 나쁘기 때문에 항목을 짐작으로 채우지 않고 워크플로우 단계마다 읽는 파일을 보고 뽑았다.

코틀린 소스, Gradle 스크립트, Gradle 디렉토리는 당연히 들어갔고 나머지는 단계를 읽어 봐야 알 수 있었다. 워크플로우는 `tools/ci/`의 스크립트로 앱별 설정을 디코딩하고 파이썬 검사기로 flavor 목록을 읽는다. iOS 의존성 버전을 확인하는 셸 스크립트도 돌린다. 검사기는 Xcode 빌드 설정 파일과 모든 Swift 파일을 파싱하고, 셸 스크립트는 Xcode 프로젝트 파일을 읽는다. 워크플로우 어디에서도 Swift를 컴파일하지는 않지만 iOS 디렉토리의 변경이 단계를 깨뜨릴 수 있으므로 목록에 넣었다. 줄여서 옮기면 다음과 같다.

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
      - 'app/**'            # Gradle 모듈 디렉토리를 하나씩 적는다
      - 'iosApp/**'         # 버전·레지스트리 검사가 읽는다
      - 'tools/ci/**'       # 단계가 부르는 스크립트
      - 'tools/check-flavors.py'
      - 'scripts/verify-ios-versions.sh'
      - '.github/workflows/build.yml'
```

워크플로우 주석에는 단계에 무언가를 더하면 이 목록에도 더해야 한다고 적어 두었다. 허용 목록이 변경을 놓치는 건 바로 이 목록을 같이 고치지 않았을 때다.

## 같은 커밋 40개로 다시 확인

머지하기 전에 같은 스크립트로 같은 커밋 40개에 허용 목록을 돌려 봤다. 핵심 부분은 짧아서 그대로 옮긴다.

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

`ALLOW`에 실제 허용 목록 전체를 넣고 `rev`를 변경 직전 커밋으로 두면 결과는 다음과 같다.

```
paths-ignore fires: 34
allowlist fires:   14
missed Kotlin:     0
```

스크립트는 `*`와 `**`만 다루는데 두 필터 모두 그 둘만 썼다. 판정 단위도 다르다. 스크립트는 커밋을 하나씩 보지만 GitHub는 푸시 단위로 보기 때문에, 커밋 여러 개를 한 번에 푸시하면 합친 diff로 판정한다.

| 트리거 | 최근 커밋 40개 중 실행 | 놓친 코틀린/Gradle 커밋 |
|---|---|---|
| `paths-ignore` | 34 | 0 |
| `paths` 허용 목록 | 14 | 0 |

이 표본에서 실행은 59% 줄었고 놓친 커밋은 없었다. 워크플로우 사용 시간도 같은 비율로 줄어든다면 1,644 × 14 / 34로 한 달 약 680분이고, 저장소 전체로는 2,000분 한도에 약 1,160분이 된다.

## 커밋 272개에 실행 84번, 그리고 워크플로우 삭제

허용 목록은 2026-09-23에 들어갔고 워크플로우는 2026-10-05에 다시 돌기 시작했다. 그날부터 10-13 오전까지 기본 브랜치에 커밋 272개가 쌓이는 동안 워크플로우는 84번 돌았으니 약 31%다. 푸시 횟수를 커밋 수에 견준 것이라 거친 비교지만, 이력에 다시 돌려 본 35%(40개 중 14개)와 크게 다르지 않다.

사용 시간을 좌우하는 다른 하나는 커밋 수인데 이쪽이 늘었다. 9월 첫 23일 동안 커밋이 326개였는데, 다시 돌기 시작한 뒤로는 8일 반 만에 272개가 쌓였다. 결국 2026-10-13에 워크플로우를 지웠다. 그 무렵에는 같은 검사를 커밋 전에 로컬에서 한 번, 배포 전에 또 한 번 돌렸고 배포 레인은 모든 앱을 실제로 컴파일했다. CI 결과는 바이너리가 이미 스토어에 올라간 뒤에야 나왔으므로 더는 아무것도 막지 못했다. 9월에 워크플로우를 남긴 것은 깨진 커밋을 배포 도중에야 알게 될까 봐서였는데, 이제는 로컬 검사가 그 역할을 하고 있었다. 그 워크플로우에만 있던 가벼운 검사 하나는 iOS 의존성 버전 스크립트였다. 이 스크립트는 작은 하네스 워크플로우로 옮기고 그 입력 파일을 하네스 워크플로우의 경로 필터에 추가했다.

## 정리

지금은 새 경로 필터를 위 스크립트로 최근 이력에 먼저 돌려 보고, 아낀 실행 수보다 놓친 코틀린 커밋 수를 먼저 센다. 이번에도 놓친 커밋 0개로 34 → 14가 나와서 머지했다. 차단 목록 트리거도 한 번 쓰고 끝난 설정으로 보지 않는다. 이 목록은 2월에는 맞았지만 9월까지 아무도 손대지 않는 사이 최상위 디렉토리가 하나 늘 때마다 CI 비용도 늘었다.
