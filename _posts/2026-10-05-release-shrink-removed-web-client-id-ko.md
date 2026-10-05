---
title: "릴리스 빌드에서만 Google 로그인이 211번 실패한 이유"
description: "Android 릴리스 빌드에서만 Google 로그인이 211번 실패했다. getIdentifier로 찾던 문자열을 리소스 축소가 지운 과정과 AAB에서 확인하는 명령."
date: 2026-10-05 10:47:20 +0900
categories: [Android]
tags: [resource-shrinking, credential-manager, firebase-auth, google-services, gradle]
lang: ko-KR
hidden: true
mermaid: true
ref: release-shrink-removed-web-client-id
permalink: /ko/posts/release-shrink-removed-web-client-id/
math: false
---

9월 29일부터 10월 1일까지 내가 만든 앱의 Android 버전에서 Google 로그인이 211번 실패했다. 성공은 한 번도 없었다. 오류 코드는 매번 `no_web_client_id`였고, 디버그 빌드에서는 로그인이 아무 문제 없이 됐다.

원인은 문자열 리소스 하나였다. 릴리스 빌드의 리소스 축소가 그 리소스를 지웠다. 리소스를 찾는 코드는 있었지만 축소 단계가 알아볼 수 있는 방식이 아니었다.

## 클라이언트 ID가 로그인 코드에 닿기까지

앱은 Kotlin Multiplatform 프로젝트이고, Android 쪽 product flavor가 여섯 개다. AGP 9.2.1과 Kotlin 2.4.20으로 빌드하고 Android 로그인에는 Firebase Auth와 Credential Manager를 쓴다.

로그인을 선택 사항으로 둔 계정 기능을 막 배포한 참이었다. Apple이나 Google로 로그인하면 iOS에서 산 구매가 Android에서도 풀린다. Android의 Google 로그인은 Credential Manager를 거치는데, 여기에 OAuth 웹 클라이언트 ID를 `serverClientId`로 넘겨야 한다.

이 ID는 `google-services.json`에서 온다. google-services Gradle 플러그인이 이 파일을 읽어 `default_web_client_id`라는 문자열 리소스를 만든다. 다만 플러그인을 적용한 모듈에만 만들고, 내 프로젝트에서는 그게 앱 모듈이다. 로그인 코드는 Kotlin Multiplatform 공유 라이브러리 모듈에 있다. 앱 모듈에만 생기는 리소스라 라이브러리에는 생성된 `R` 항목이 없다. 그래서 `webClientId()`는 런타임에 이름으로 문자열을 찾고, 0이 나오면 바로 null을 돌려준다.

```kotlin
private fun webClientId(context: Context): String? {
    val id = context.resources.getIdentifier(
        "default_web_client_id", "string", context.packageName
    )
    if (id == 0) return null
    return context.getString(id).takeIf { it.isNotBlank() }
}

// 호출하는 쪽
val clientId = webClientId(context) ?: return Failed("no_web_client_id")
```

오류 코드는 일부러 이렇게 정했다. Firebase 콘솔에서 Google 제공자를 켜고 `google-services.json`을 다시 받기 전까지는 이 리소스가 정말로 없다. `no_web_client_id`는 "설정 단계를 하나 빠뜨렸다"는 뜻으로 만든 코드였다.

## 빌드 단계마다 값을 따라가 봤다

첫 신고는 앱 안의 문의 양식으로 들어왔다. 계정 연결 실패 이벤트에는 오류 코드가 실리므로 릴리스 이후 기간을 BigQuery로 조회했다. Android 실패는 전부 `no_web_client_id`였고 실패 211번, 성공 0번이었다. 같은 기간 iOS에서는 로그인이 정상으로 끝났다.

"설정이 빠졌다"는 코드였으니 빠진 설정부터 찾았다. 설정은 다 있었다. 그래서 값이 지나가는 단계를 빌드 순서대로 하나씩 봤다. 생성 단계까지는 모두 "있음"이고 배포한 AAB에서만 "없음"이다.

| 단계 | `default_web_client_id` 있음? |
|---|---|
| `google-services.json`, flavor 여섯 개 모두 | 있음 (OAuth 클라이언트 type 3 항목) |
| `process<Flavor>ReleaseGoogleServices` 산출물 | 있음 |
| 디버그 APK (축소 없음) | 있음 |
| 배포한 2.2.85 릴리스 AAB의 `base/resources.pb`, flavor 두 개 | 없음 |

생성된 리소스까지는 모든 단계에 문자열이 있었고, 축소를 지나자 사라졌다. 릴리스 빌드 타입은 `isMinifyEnabled = true`, `isShrinkResources = true`였다. 디버그는 둘 다 꺼져 있었다.

## 축소 단계가 따라가지 못한 이름

리소스 축소는 쓰인다고 증명하지 못한 리소스를 지운다. `R.string.default_web_client_id`로 참조하면 축소 단계가 따라갈 수 있다. 런타임에 `getIdentifier`로 넘기는 이름은 그냥 문자열이다. 게다가 여기서는 리소스가 생기는 모듈과 그 리소스를 찾는 코드의 모듈이 다르다.

리소스 축소 문서에는 코드에 문자열 리터럴로 나오는 이름의 리소스를 남기는 "safe" 모드가 나온다. 그래서 이 조회는 지워지지 않을 줄 알았다. AGP 9.2.1과 내 구성에서는 지워졌다. 축소된 AAB에서 이 이름은 한 번도 나오지 않았다.

디버그와 릴리스에서 같은 리소스가 어떻게 되는지 그려 보면 이렇다.

```mermaid
flowchart LR
  J[google-services.json] --> G[플러그인이 앱 모듈에<br/>default_web_client_id 생성]
  G --> D[디버그: 축소 없음] --> OK1[getIdentifier가 찾음]
  G --> R[릴리스: isShrinkResources] --> Q{축소기가 볼 수 있는<br/>참조가 있나}
  Q -- 없음 --> X[삭제] --> F[getIdentifier가 0 반환<br/>no_web_client_id]
  Q -- tools:keep --> OK2[유지] --> OK3[로그인 성공]
```

## 릴리스 점검도 실기기 확인도 통과했다

버전마다 돌리는 릴리스 점검은 diff를 기준으로 한다. 직전 배포 커밋과 HEAD 사이의 `git diff --name-only`를 읽고 보안 규칙과 스키마, 광고·페이월 진입점 같은 영역별로 티켓을 만든다. 2.2.85 점검은 실패 0건으로 끝났다. 빌드 도중에 사라지는 리소스는 diff에 나오지 않는다. 이 점검으로는 볼 수 없는 버그였다.

출시 다음 날 실기기에서도 로그인이 잘 됐다. 디버그 빌드는 리소스를 축소하지 않는다. 이런 버그는 기기에 릴리스 빌드를 깔아야 실기기 확인에서 걸린다.

## `tools:keep`으로 문자열 남기기

앱 모듈 main 소스 세트에 XML 파일 하나를 넣어 축소 단계가 이 문자열을 남기게 했다.

```xml
<!-- res/raw/keep_auth.xml -->
<resources xmlns:tools="http://schemas.android.com/tools"
    tools:keep="@string/default_web_client_id" />
```

파일 이름을 `keep.xml`로 하지 않은 데는 이유가 있다. flavor 여섯 개 중 다섯 개에 다른 리소스용 `res/raw/keep.xml`이 이미 있었다. flavor 소스 세트에 같은 이름의 리소스가 있으면 `main` 쪽을 덮어쓴다. `main/res/raw/keep.xml`로 만들었다면 그 다섯 flavor에서는 경고 하나 없이 덮어써졌을 것이다. 이름이 다르면 둘 다 남는다.

수정은 Android 전용 핫픽스 2.2.86으로 나갔다. 그 뒤에 머지된 관계없는 기능이 같이 실리지 않도록 이전 master 커밋에서 브랜치를 땄다. iOS에는 같은 결함이 없어서 다시 빌드하지 않았다.

## AAB에서 이름을 세어 봤다

소스 트리로는 결론이 나지 않는다. 릴리스 번들을 직접 풀어 이름이 몇 번 나오는지 셌다.

```bash
unzip -q -o app/build/outputs/bundle/<flavor>Release/app-<flavor>-release.aab \
  base/resources.pb -d /tmp/aab
strings /tmp/aab/base/resources.pb | grep -c default_web_client_id
```

| 빌드 | `grep -c` 출력 | Android Google 로그인 |
|---|---|---|
| 2.2.85 릴리스 AAB | 0 | 실패 211번, 성공 0번 (9월 29일~10월 1일) |
| `keep_auth.xml`을 넣은 릴리스 AAB | 1 | 2.2.86에서 수정 |

처음에는 macOS에서 `unzip -p ... | strings | grep -c ...`로 쓰려고 했다. 내 맥에서는 파이프로 받은 입력에 macOS `strings`가 빈 출력을 냈고 `grep -c`도 아무것도 찍지 않았다. 일치 0건처럼 보이지만 `strings`에 들어간 입력 자체가 없었다. 파일로 먼저 풀고 경로를 넘기면 이 문제를 피한다.

## 오류 코드는 가설 하나로 둔다

오류 코드는 틀린 말을 하지 않았다. 엉뚱한 데를 판 건 나였다. `no_web_client_id`는 코드가 본 그대로였지만, 나는 거기에 "설정 단계를 빠뜨렸다"는 원인 하나만 붙여 두었다. 오류 코드가 원인을 짐작해 주더라도 지금은 그걸 가설 하나로만 둔다. 확인은 빌드 단계마다 값을 직접 본다.

`getIdentifier`, 리플렉션, 네이티브 코드나 다른 모듈에서만 참조하는 리소스도 같은 위험이 있다. 디버그와 릴리스는 바로 이런 걸 걷어내는 단계에서 갈린다. 디버그 빌드로는 이 버그가 보이지 않는다. 이번 경우는 위의 셸 두 줄이면 됐고, 이 검사만 있었어도 2.2.85는 업로드 전에 걸렸다. 디버그에서는 되는데 릴리스에서만 안 된다면 `resources.pb`부터 열어 보길 권한다.
