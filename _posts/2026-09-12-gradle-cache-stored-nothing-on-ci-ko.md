---
title: "GitHub Actions Gradle 캐시가 저장되지 않는 문제"
description: "GitHub Actions에서 Gradle 빌드는 매번 성공했는데 캐시 목록은 비어 있었다. setup-gradle v3가 캐시 복원과 저장에 모두 실패하고도 경고만 남긴 것이 원인이어서 v5로 고정했다."
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

GitHub Actions에서 도는 Kotlin Multiplatform 프로젝트에 Gradle 빌드 캐시를 켜고 푸시했다. CI는 통과했는데 `gh cache list`에는 Gradle 캐시가 하나도 없었다. 복원도 저장도 전부 실패했는데, 액션이 실패할 때마다 경고만 남기고 넘어갔기 때문에 실행 결과만 봐서는 알 수 없었다.

## 같은 코틀린 코드를 두 번 컴파일하던 job

프로젝트는 안드로이드와 iOS를 함께 내는 Compose Multiplatform 앱이고 비공개 저장소에 있다. 비공개 저장소는 Actions 무료 사용 시간이 한 달 단위로 정해져 있는데 이 프로젝트는 그 한도 안에서 돌았다. 그래서 줄여야 할 것은 전체 소요 시간보다 과금되는 Actions 사용 시간(분)이었다.

워크플로우는 기본 브랜치에 푸시할 때만 돌았고 `ubuntu-latest`에 빌드 job이 둘 있었는데, `build-android`는 `test`가 끝나기를 기다렸다. 손대기 전 마지막으로 성공한 실행에서 `test`는 10분 39초, `build-android`는 13분 47초가 걸렸다. 뒤쪽 job은 앞 job이 방금 컴파일한 코틀린 코드를 새 러너에서 다시 컴파일하느라 시간을 많이 썼는데, 앞 job의 러너는 이미 버려진 뒤였다.

그래서 한 커밋에서 두 가지를 바꿨다.

1. 두 job을 하나로 합쳤다. test 단계에서 만든 출력을 assemble 단계가 Gradle의 `UP-TO-DATE` 검사만으로 그대로 재사용하게 하려는 것이다. 로컬에서 `clean` 뒤 합친 순서로 돌려 보니 assemble 단계 태스크 334개 중 253개가 `UP-TO-DATE`였다.
2. `org.gradle.caching=true`를 켰다. `UP-TO-DATE` 검사는 같은 러너 안에서만 의미가 있으므로 다음 실행으로 출력을 넘기려면 캐시가 필요했다. `gradle/actions/setup-gradle`은 원래 Gradle User Home을 저장하고 복원하는데 그 안에 로컬 빌드 캐시 디렉토리(`caches/build-cache-1`)가 들어 있다. 워크플로우가 기본 브랜치에서만 돌기 때문에 액션은 캐시를 읽기 전용으로 쓰지 않고 캐시 엔트리를 저장한다. 로컬에서는 clean 빌드의 태스크 433개 중 117개를 캐시에서 가져왔다.

다만 117/433을 CI 절감량으로 환산하지는 않았다. 노트북에는 데몬이 떠 있고 의존성도 받아져 있지만 GitHub 호스팅 러너에는 둘 다 없으므로, CI에서 얼마나 줄어드는지는 변경 뒤 첫 실행에서 재 보기로 했다.

두 job을 병렬로 돌리면 끝나는 시각은 당겨져도 과금되는 시간은 그대로다. 무료 한도는 사용 시간(분)을 세기 때문에 병렬로 돌리는 안은 버렸다.

## 첫 실행의 Setup Gradle 로그

변경 뒤 첫 실행은 성공했고, 합친 build job은 15분 25초가 걸려 시간이 실제로 어느 정도 줄었다. 그런데 `Setup Gradle` 단계와 post 단계의 로그를 열어 보니 워크플로우가 아직 `setup-gradle@v3`를 쓰고 있었고, 복원 단계에는 다음과 같은 줄이 있었다.

```
Failed to restore gradle-home-v1|Linux|build[…]: Cache service responded with 400
```

post 단계에서는 저장할 때마다 캐시 응답 대신 GitHub의 HTML 에러 페이지("Our services aren't available right now")가 돌아왔다. 전부 경고였기 때문에 job은 `success`로 끝났다. 캐시 목록도 비어 있었다.

```bash
gh cache list --key gradle-home
# 엔트리 없음
```

처음에는 캐시 서비스 장애가 아닐까 의심했다. 그런데 같은 저장소의 다른 워크플로우가 같은 주에 pip 캐시를 저장했고, 그 캐시 엔트리는 `gh cache list`에 멀쩡히 있었다. 캐시 서비스는 저장 요청을 정상적으로 받고 있었으니, 이 버전의 액션만 캐시 서비스에 접근하지 못한 것이다. v3는 메이저 버전으로 셋이나 뒤처져 있었고 post 단계에서는 Node 20 지원 종료 경고도 나왔다.

post 단계는 푸시할 때마다 저장을 시도하느라 1분쯤 썼지만 남은 것은 없었다. 빌드는 내내 성공으로 떴으니 들여다볼 계기도 없었다.

## v6 대신 v5 고정

버전을 올릴 때 v6도 이미 나와 있었지만 고르지 않았다. v6은 캐싱 기능을 별도의 독점 컴포넌트(`gradle-actions-caching`)로 옮겼고, 그 라이선스 조건에 동의해야 쓸 수 있다. 동의해도 괜찮을 수 있지만 라이선스 동의는 버그 수정과 별개의 결정이므로 버전을 올리는 김에 같이 정할 일은 아니라고 봤다. v5에는 캐싱이 아직 들어 있어서 v5로 고정했다.

```yaml
- name: Setup Gradle
  uses: gradle/actions/setup-gradle@v5
```

```properties
# gradle.properties
org.gradle.caching=true
```

단계 위에는 v6이 아니라 v5를 쓰는 이유를 주석으로 적어 두었다. 다음에 버전을 올리는 사람이 변경 로그보다 라이선스 문제를 먼저 읽게 하려는 것이다.

## v5가 복원한 캐시

이 글을 쓰면서 `gh run view <id> --log`로 실행 로그를 다시 열어 봤다. 캐시를 켰다고 캐시가 쓰이는 것이 아니었듯, 버전을 올렸다고 문제가 풀렸다고 볼 수도 없기 때문이다. v5로 바꾼 뒤 첫 두 실행은 예상대로 빈 캐시에서 시작했다.

```
Gradle User Home cache not found. Will initialize empty.
```

세 번째 실행은 첫 v5 실행이 저장을 마친 뒤에 시작했고 실제 캐시 엔트리를 복원했다.

```
Cache hit for restore-key: gradle-home-v1|Linux-X64|build[…]-<sha>
Cache Size: ~101 MB (106283039 B)
Cache restored successfully
```

build job 소요 시간은 `gh run view <id> --json jobs`에서 `completedAt`과 `startedAt`의 차이로 구했다. 결과는 다음과 같다.

| 실행 수 | 구성 | build job 소요 시간 |
|---|---|---|
| 1 | job 둘, v3, 빌드 캐시 없음 | 10분 39초 + 13분 47초 (순차) |
| 1 | job 하나, v3, 캐시는 켰지만 저장된 것 없음 | 15분 25초 |
| 2 | job 하나, v5, 빈 캐시 (첫 저장) | 16분 56초, 17분 21초 |
| 100 | job 하나, v5, 캐시가 채워진 뒤, 2026-09-12~09-23 | 중앙값 6분 51초, 범위 3분 02초~15분 16초 |

job을 합친 덕분에 순차로 24분쯤 걸리던 작업이 15분 25초로 줄었는데, 이때까지 캐시 덕분에 줄어든 시간은 없었다. 캐시가 제대로 쓰이기 시작한 뒤에는 합친 job이 15~17분에서 중앙값 7분 아래로 내려왔다. 캐시가 채워진 뒤의 실행 100번 중 26번은 5분 이하, 70번은 5~10분이었고 4번은 10분을 넘겼다.

## 1MB짜리 캐시 히트

10분을 넘긴 네 번 중 세 번은 같은 날 저녁에 연달아 돌았다. 세 실행 모두 1MB쯤 되는 Gradle User Home 엔트리를 복원했는데, 그날 앞선 실행들은 62MB 안팎을 복원했었다. 그 저녁에는 실행 세 번이 Gradle 단계에 들어가기도 전에 셸 검사에서 2분 안에 실패했고, 느린 실행은 세 번째 실패 바로 뒤부터 이어졌다. 느린 실행이 지나간 뒤 처음 성공한 실행은 102MB쯤을 복원했고 3분 23초 만에 끝났다.

로그는 이 실행들을 모두 캐시 히트로 표시했다. 그날 정상 엔트리는 1MB 엔트리보다 50배 넘게 컸지만 실행 결과는 어느 쪽이든 똑같이 성공으로 떴다.

## 캐시 엔트리와 크기 확인

캐시는 원래 없어도 빌드가 돌도록 만든 장치다. 그러니 캐시 백엔드에 접근하지 못한 setup-gradle이 빌드를 계속 진행하는 것은 맞는 동작이고, 캐시가 실제로 쓰이는지 보는 검사는 액션 바깥에 둘 수밖에 없다. 프로젝트 CI 문서에는 `gh cache list`에 엔트리가 보여야 캐시가 켜진 것으로 본다고 적었고, 1MB짜리 캐시가 복원된 그날 저녁을 겪은 뒤로는 크기도 함께 본다. 기본 브랜치 빌드 뒤에 다음 스크립트를 돌리면 엔트리가 없거나 너무 작을 때 단계가 실패한다.

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

기준값은 각자 로그에서 정상 엔트리가 얼마나 되는지 보고 정하는 것이 좋다. 내 경우는 62MB에서 102MB 사이였다.

## 정리

v3 실패를 첫 실행에서 잡은 것은 job 소요 시간을 보다가 마침 캐시 단계 로그를 열었기 때문이다. 지금은 변경을 넣기 전에 적용됐는지 확인할 지표부터 정해 두고, 성공 표시만 보지 않고 그 지표를 직접 확인한다. 이번 캐시 작업에서는 캐시 엔트리와 그 크기가, v5 고정에서는 라이선스 조건이 그 지표였다.

Actions 사용 시간은 11일 뒤에 결국 모자랐는데 캐시와는 상관없는 이유였다. 그 이야기는 [paths-ignore 글](/ko/posts/ci-minutes-paths-ignore-blocklist/)에 따로 썼다.
