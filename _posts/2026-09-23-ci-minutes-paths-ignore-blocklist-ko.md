---
title: "항목 셋짜리 paths-ignore가 CI 사용 시간의 77%를 썼다"
description: "8분짜리 Kotlin 빌드가 커밋 40개 중 34개에서 돈 건 차단 목록 트리거 탓이었다. 사용 시간을 재고 허용 목록을 git 이력에 재생해 본 뒤 바꿨다."
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

GitHub Actions 워크플로 하나가 저장소의 월간 예상 사용 시간 중 77%를 쓰고 있었다. 최근 커밋 40개 중 34개에서 8분짜리 Kotlin 컴파일이 돌았는데, 그 40개 중 Kotlin이나 Gradle을 조금이라도 건드린 커밋은 12개뿐이었다. 빌드 한 번은 이미 싸게 만들어 둔 뒤였다. 분을 잡아먹은 건 항목 셋짜리 `paths-ignore` 트리거였다.

## 시작도 못 하고 실패한 실행

저장소는 비공개이고 Kotlin Multiplatform 앱과 그 주변이 전부 들어 있다. Python 도구, 에이전트 스킬 파일, 정적 사이트, 마케팅 자료, 어드민 도구, Cloud Functions까지 있다. 비공개 저장소에는 Actions 무료 사용 시간이 매달 정해져 있고 이 요금제에서는 2,000분이다. 2026-09-23부터 모든 실행이 첫 단계에 들어가기도 전에 이 메시지를 내고 실패했다.

```
The job was not started because recent account payments have failed or your
spending limit needs to be increased.
```

문구만 보면 결제 문제다. 설정을 건드리기 전에 무료 한도를 다 쓴 건지부터 알고 싶었다. 그래서 2026-09-19부터 09-23까지 닷새 동안 과금된 job 분을 재서 한 달로 늘려 봤다. 2,000분 한도에 약 2,129분이 나왔다. 그중 1,644분, 77%가 Kotlin 빌드·테스트 워크플로 하나에서 나왔다. 한도 소진으로 보는 게 자연스러웠고 어디를 줄일지도 분명했다.

이 워크플로의 실행 시간은 job을 합치고 빌드 캐시를 제대로 돌려서 이미 줄여 둔 상태였다. 그 과정은 [다른 글](/ko/posts/gradle-cache-stored-nothing-on-ci/)에 썼다. 보통 한 번 도는 데 7분 안팎이었다. 남은 건 몇 번 도느냐였다.

## 2월에 22개, 9월에 51개

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

Cloud Functions와 문서만 빼고 나머지 변경은 전부 Kotlin 빌드를 띄웠다. 이 목록은 2월에 내가 썼다. 버전 카탈로그와 SQL 스키마 디렉터리만 보던 항목 둘짜리 허용 목록을 "이것만 빼고 모든 푸시"로 바꾸면서 생긴 목록이다. 평범한 코드 변경에도 CI가 돌게 하려고 그랬다. 2월에 저장소 최상위 항목은 22개였다. 9월에는 51개가 됐고 새로 생긴 항목은 대부분 Kotlin과 상관이 없었다. `tools/`, `.claude/skills/`, `site/`, `marketing/`, `admin/`, 앱 문구를 모은 `COPY.yaml` 같은 것들이다. 이 항목들이 하나같이 8분짜리 컴파일을 띄웠다. 목록은 아무도 고치지 않았고 그 주위로 트리만 자랐다.

얼마나 자주 그랬는지 보려고 최근 커밋 40개를 필터에 다시 흘려 봤다. 작은 스크립트가 `git log --name-only`에서 커밋마다 바뀐 파일을 읽고 GitHub의 glob 규칙으로 맞춰 본다. 이 규칙에서 `*`는 슬래시를 넘지 않고 `**`는 넘는다.

| 트리거 | 최근 커밋 40개 중 실행 |
|---|---|
| `paths-ignore` (functions, docs, `*.md`) | 34 |
| Kotlin이나 Gradle을 건드린 커밋 | 12 |

40개 중 28개(70%)는 Kotlin도 Gradle도 바꾸지 않았는데 그 대부분이 빌드 비용을 냈다.

## 컴파일 관문은 남겼다

워크플로를 지우면 분을 가장 많이 아낀다. 9월에는 그러지 않기로 했다. 이 프로젝트에는 스테이징 환경이 없고 스토어 배포는 로컬에서 Fastlane으로 한다. 컴파일 관문이 없으면 컴파일이 안 되는 Kotlin 커밋을 배포 도중에야 알게 된다. 워크플로는 그걸 더 일찍 잡으려고 있었다. 그러려면 빌드를 깨뜨릴 수 있는 커밋에서만 돌면 됐다.

훨씬 싼 워크플로도 하나 있었다. 새로 클론한 저장소에서 저장소 규칙을 강제하는 하네스 검사인데, 한 번에 1분쯤 들고 전체의 7%였다. 이건 그대로 뒀다.

## 단계가 읽는 파일로 허용 목록 만들기

필터를 뒤집어서 빌드를 띄우지 않을 경로 대신 띄울 경로를 적었다. 그러면 실수했을 때 치르는 값이 달라진다. 예전 목록에서 항목을 빼먹으면 필요 없는 빌드 값을 냈다. 허용 목록에서 빼먹으면 진짜 변경이 아무 경고 없이 관문을 건너뛴다. 이쪽이 더 나빠서 항목을 짐작으로 채우지 않았다. 워크플로 단계마다 읽는 파일을 보고 목록을 뽑았다.

Kotlin 소스, Gradle 스크립트, Gradle 디렉터리는 당연했다. 나머지는 단계를 읽어 봐야 나왔다. 워크플로는 `tools/ci/`의 스크립트로 앱별 설정을 풀고, Python 검사기로 flavor 목록을 읽는다. iOS 의존성 버전을 확인하는 셸 스크립트도 돌린다. 그 검사기는 Xcode 빌드 설정 파일과 모든 Swift 파일을 파싱하고 셸 스크립트는 Xcode 프로젝트 파일을 읽는다. 워크플로 어디서도 Swift를 컴파일하지 않는다. 그래도 iOS 디렉터리의 변경이 단계를 깨뜨릴 수 있어서 목록에 넣었다. 줄여서 옮기면 이렇다.

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
      - 'app/**'            # Gradle 모듈 디렉터리를 하나씩 적는다
      - 'iosApp/**'         # 버전·레지스트리 검사가 읽는다
      - 'tools/ci/**'       # 단계가 부르는 스크립트
      - 'tools/check-flavors.py'
      - 'scripts/verify-ios-versions.sh'
      - '.github/workflows/build.yml'
```

워크플로 주석에는 단계에 무언가를 더하면 이 목록에도 더해야 한다고 적어 두었다. 허용 목록이 변경을 놓치는 건 그 편집을 빼먹었을 때다.

## 같은 커밋 40개에 다시 흘려 보기

병합 전에 같은 스크립트로 같은 커밋 40개에 허용 목록을 흘려 봤다. 핵심은 보여 줄 만큼 짧다.

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

`ALLOW`에 실제 허용 목록 전체를 넣고 `rev`를 변경 직전 커밋으로 두면 이렇게 나온다.

```
paths-ignore fires: 34
allowlist fires:   14
missed Kotlin:     0
```

스크립트는 `*`와 `**`만 다루는데 두 필터 모두 그 둘만 썼다. 판정 단위도 다르다. 스크립트는 커밋 하나씩 보지만 GitHub는 푸시 단위로 보기 때문에 커밋 여러 개를 한 번에 푸시하면 합친 diff로 판정한다.

| 트리거 | 최근 커밋 40개 중 실행 | 놓친 Kotlin/Gradle 커밋 |
|---|---|---|
| `paths-ignore` | 34 | 0 |
| `paths` 허용 목록 | 14 | 0 |

이 표본에서 실행은 59% 줄었고 놓친 커밋은 없었다. 같은 비율로 워크플로의 분을 줄이면 1,644 × 14 / 34로 한 달 약 680분이다. 저장소 전체로는 2,000분 한도에 약 1,160분이 된다.

## 커밋 272개에 84번, 그리고 워크플로 삭제

허용 목록은 2026-09-23에 들어갔다. 워크플로는 2026-10-05에 다시 돌기 시작했다. 그날부터 10-13 오전까지 기본 브랜치에 커밋 272개가 쌓이는 동안 워크플로는 84번 돌았다. 약 31%다. 푸시와 커밋을 견준 수치라 거친 비교지만 재생 검증의 35%(40개 중 14개)와 크게 다르지 않다.

비용의 나머지 절반은 커밋 수인데 그쪽은 늘었다. 9월 첫 23일 동안 커밋은 326개였고 다시 돌기 시작한 뒤로는 8일 반 만에 272개였다. 결국 2026-10-13에 워크플로를 지웠다. 그 무렵에는 같은 검사를 커밋 전에 로컬에서 한 번, 배포 전에 또 한 번 돌렸다. 배포 레인은 모든 앱을 실제로 컴파일했다. CI 판정은 바이너리가 이미 스토어에 올라간 뒤에야 도착했으니 더는 아무것도 막지 못했다. 9월에 워크플로를 남긴 건 깨진 커밋을 배포 도중에야 알게 될까 봐서였는데, 그 걱정은 로컬 관문이 덜어 줬다. 그 워크플로에만 있던 싼 검사 하나는 iOS 의존성 버전 스크립트였다. 이 스크립트는 작은 하네스 워크플로로 옮기고 그 입력 파일을 하네스 워크플로의 경로 필터에 더했다.

## 지금 경로 필터를 바꿀 때

새 필터는 위 스크립트로 최근 이력에 먼저 흘려 보고 절감한 실행보다 놓친 Kotlin 커밋부터 센다. 이번에도 놓친 커밋 0건으로 34 → 14가 나와서 병합했다. 차단 목록 트리거는 한 번 쓰고 끝난 설정으로 보지 않는다. 이 목록은 2월에는 맞았다. 9월까지 아무도 손대지 않았고 최상위 디렉터리가 하나 늘 때마다 비싸졌다.
