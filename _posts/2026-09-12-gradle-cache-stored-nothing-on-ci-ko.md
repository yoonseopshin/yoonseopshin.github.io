---
title: "CI는 초록인데 Gradle 캐시 엔트리는 0건이었다"
description: "setup-gradle v3는 캐시 복원과 저장이 모두 실패해도 경고만 남겼고 job은 초록이었다. 로그에서 알아챈 과정과 v5로 고정한 이유를 적었다."
date: 2026-09-12 13:46:53 +0900
categories: [Build & CI]
tags: [gradle, github-actions, build-cache, kotlin-multiplatform, ci]
lang: ko-KR
hidden: true
mermaid: false
ref: gradle-cache-stored-nothing-on-ci
permalink: /ko/posts/gradle-cache-stored-nothing-on-ci/
math: false
---

GitHub Actions에서 도는 Kotlin Multiplatform 프로젝트에 Gradle 빌드 캐시를 켜고 푸시했다. run은 초록이었는데 `gh cache list`에 Gradle 엔트리는 0건이었다. 복원도 저장도 전부 실패했지만 액션은 실패를 하나하나 경고로만 찍었다. run 상태만 봐서는 알 길이 없었다.

## 같은 Kotlin을 두 번 컴파일하던 job 둘

프로젝트는 Android와 iOS를 함께 내는 Compose Multiplatform 앱이고 비공개 저장소에 있다. 비공개 저장소는 Actions 무료 사용 시간이 한 달 단위로 정해져 있는데, 이 프로젝트는 그 안에서 돌았다. 그래서 줄일 것은 벽시계 시간보다 러너 분이었다.

워크플로는 기본 브랜치 푸시에서만 돌았고 `ubuntu-latest`에 빌드 job이 둘 있었다. `build-android`는 `test`가 끝나기를 기다렸다. 손대기 전 마지막 성공 run에서 `test`는 10분 39초, `build-android`는 13분 47초가 걸렸다. 뒤 job은 앞 job이 방금 컴파일한 Kotlin을 새 러너에서 다시 컴파일하느라 시간을 많이 썼다. 앞 job의 러너는 이미 버려진 뒤였다.

한 커밋에서 두 가지를 바꿨다.

1. 두 job을 하나로 합쳤다. 조립 단계가 테스트 단계의 출력을 Gradle의 평범한 up-to-date 검사로 재사용하게 하려고 그렇게 했다. 로컬에서 `clean` 뒤 합친 순서로 돌리니 조립 단계 태스크 334개 중 253개가 up-to-date였다.
2. `org.gradle.caching=true`를 켰다. up-to-date 검사는 러너 하나 안에서만 통하니 run 사이로 출력을 넘기려면 캐시가 있어야 했다. `gradle/actions/setup-gradle`은 원래 Gradle User Home을 저장하고 복원하는데, 그 안에 로컬 빌드 캐시 디렉터리(`caches/build-cache-1`)가 들어 있다. 워크플로가 기본 브랜치에서만 도니 액션은 캐시를 읽기 전용으로 열지 않고 엔트리를 쓴다. 로컬에서는 clean 빌드의 태스크 433개 중 117개가 캐시에서 나왔다.

117/433을 CI 절감량으로 환산하지는 않았다. 노트북에는 데몬이 떠 있고 의존성도 받아져 있지만 호스티드 러너에는 둘 다 없다. CI 효과는 변경 뒤 첫 run에서 재기로 했다.

두 job을 병렬로 돌리면 벽시계 시간은 줄어도 분은 그대로다. 무료 한도는 분을 세니 병렬안은 버렸다.

## 첫 run의 Setup Gradle 로그

변경 뒤 첫 run은 초록이었고 합친 build job은 15분 25초 걸렸다. 일부는 진짜로 나아진 몫이었다. 그러다 `Setup Gradle` 단계와 post 단계 로그를 열었다. 워크플로는 아직 `setup-gradle@v3`였고 복원 단계에 이런 줄이 있었다.

```
Failed to restore gradle-home-v1|Linux|build[…]: Cache service responded with 400
```

post 단계에서는 저장할 때마다 캐시 응답 대신 GitHub의 HTML 오류 페이지("Our services aren't available right now")가 돌아왔다. 모두 경고였고 job 결론은 `success`였다. 캐시 목록도 비어 있었다.

```bash
gh cache list --key gradle-home
# 엔트리 없음
```

처음에는 캐시 서비스 장애라고 생각했다. 그런데 같은 저장소의 다른 워크플로가 같은 주에 pip 캐시를 썼고, 그 엔트리는 `gh cache list`에 멀쩡히 있었다. 서비스는 쓰기를 받고 있었다. 이 버전의 액션만 서비스와 통하지 못했다. v3는 메이저 버전으로 셋이나 뒤처져 있었고 post 단계는 Node 20 지원 종료 경고도 냈다.

post 단계는 푸시마다 1분쯤을 저장 시도에 쓰고 아무것도 남기지 못했다. 빌드가 내내 초록이었으니 들여다볼 일도 없었다.

## v6이 나와 있었지만 v5로 고정했다

버전을 올릴 때 v6도 이미 나와 있었지만 고르지 않았다. v6은 캐싱을 별도의 독점 컴포넌트(`gradle-actions-caching`)로 옮기고 그 라이선스에 동의하라고 요구한다. 동의해도 괜찮을 수 있다. 다만 라이선스 동의는 버그 수정과 다른 결정이고 버전을 올리다 덤으로 내릴 일은 아니라고 봤다. v5에는 캐싱이 아직 들어 있어서 v5로 고정했다.

```yaml
- name: Setup Gradle
  uses: gradle/actions/setup-gradle@v5
```

```properties
# gradle.properties
org.gradle.caching=true
```

단계 위 주석에는 왜 v5이고 왜 v6이 아닌지 적어 두었다. 다음에 버전을 올리는 사람이 변경 기록보다 라이선스 문제를 먼저 읽었으면 해서다.

## v5가 복원한 것

이 글을 쓰면서 `gh run view <id> --log`로 run 로그를 다시 열었다. 버전을 올렸다는 사실도 캐시를 켰다는 사실만큼이나 증명하는 게 없었다. v5 첫 두 run은 예상대로 빈 캐시에서 시작했다.

```
Gradle User Home cache not found. Will initialize empty.
```

세 번째 run은 첫 v5 run이 저장을 마친 뒤에 시작했고 진짜 엔트리를 복원했다.

```
Cache hit for restore-key: gradle-home-v1|Linux-X64|build[…]-<sha>
Cache Size: ~101 MB (106283039 B)
Cache restored successfully
```

build job 소요 시간은 `gh run view <id> --json jobs`의 `completedAt`에서 `startedAt`을 빼서 구했다.

| run 수 | 구성 | build job 소요 |
|---|---|---|
| 1 | job 둘, v3, 빌드 캐시 없음 | 10분 39초 + 13분 47초 (순차) |
| 1 | job 하나, v3, 캐시는 "켜짐"이지만 저장 0건 | 15분 25초 |
| 2 | job 하나, v5, 빈 캐시 (첫 저장) | 16분 56초, 17분 21초 |
| 100 | job 하나, v5, 데워진 캐시, 2026-09-12~09-23 | 중앙값 6분 51초, 범위 3분 02초~15분 16초 |

job 병합은 순차로 24분쯤 걸리던 작업을 15분 25초로 줄였고 여기에 캐시가 보탠 것은 없었다. 캐시가 제대로 돌기 시작하자 job 하나가 15~17분에서 중앙값 7분 아래로 내려왔다. 데워진 run 100건 중 26건은 5분 이하, 70건은 5~10분이었고 4건은 10분을 넘겼다.

## 1MB짜리 캐시 적중

10분을 넘긴 네 건 중 세 건은 같은 날 저녁에 연달아 돌았다. 세 run 모두 1MB쯤 되는 Gradle User Home 엔트리를 복원했다. 그날 앞선 run들은 62MB 안팎을 복원했었다. 그 저녁에는 앞서 run 세 건이 Gradle 단계에 닿기도 전에 셸 검사에서 2분 안에 실패했고, 느린 run은 세 번째 실패 바로 뒤부터 이어졌다. 느린 run들 다음의 첫 성공 run은 102MB쯤을 복원하고 3분 23초 만에 끝났다.

로그는 이 run들을 전부 캐시 적중이라고 했다. 그날 정상 엔트리는 1MB 엔트리보다 50배 넘게 컸다. run 상태는 어느 쪽이든 똑같았다.

## 엔트리와 크기를 보는 스크립트

캐시는 없어도 빌드가 돌게 만든 장치다. 그러니 백엔드에 닿지 못한 setup-gradle이 빌드를 계속 진행시키는 건 맞는 동작이고, 캐시가 도는지 보는 검사는 액션 바깥에 둘 수밖에 없다. 프로젝트 CI 문서에는 `gh cache list`에 엔트리가 보여야 캐시가 켜진 것으로 친다고 적었다. 1MB 저녁을 겪은 뒤로는 크기도 함께 본다. 기본 브랜치 빌드 뒤에 아래 스크립트를 돌리면 엔트리가 없거나 너무 작을 때 단계가 실패한다.

```bash
#!/usr/bin/env bash
# 가장 최근 Gradle home 캐시 엔트리가 없거나 너무 작으면 실패한다.
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

기준값은 각자 로그에서 정상 엔트리가 얼마나 되는지 보고 정하면 된다. 내 경우는 62MB에서 102MB 사이였다.

v3 실패를 첫 run에서 잡은 건 job 시간을 보다가 캐시 단계 로그를 연 덕분이었다. 지금은 변경을 넣기 전에 그 변경이 통했음을 보여 줄 산출물부터 정해 두고, 상태 배지 대신 그 산출물을 연다. 이번 캐시라면 엔트리와 그 크기였다. v5 고정이라면 라이선스였다.

분은 11일 뒤에 결국 모자랐는데 캐시와는 상관없는 이유였다. 그 이야기는 [다른 글](/ko/posts/ci-minutes-paths-ignore-blocklist/)에 따로 썼다.
