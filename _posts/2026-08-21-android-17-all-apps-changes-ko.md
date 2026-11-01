---
title: "안드로이드 17 targetSdk와 무관하게 적용되는 동작 변경"
description: "targetSdk를 36에 두고 안드로이드 17 대응을 미뤘는데, 모든 앱에 적용되는 동작 변경 아홉 개 중 두 개가 코드 수정을 요구했다. 타겟 페이지만 읽고 all-apps 페이지를 건너뛴 탓이다."
date: 2026-08-21 23:08:16 +0900
categories: [Android]
tags: [android-17, targetsdk, compose, ime, applicationexitinfo]
lang: ko-KR
hidden: true
mermaid: false
ref: android-17-all-apps-changes
permalink: /ko/posts/android-17-all-apps-changes/
math: false
---

7월에 앱을 안드로이드 17 기준으로 점검했는데 필수 코드 수정은 0건이었으므로, 새 동작이 아직 사용자에게 적용되지 않도록 `targetSdk`는 일부러 36에 두었다. 그런데 3주 뒤에 보니 안드로이드 17 변경 두 개는 `targetSdk` 36에서도 모든 안드로이드 17 기기에 그대로 적용되고 있었다. 하나는 회전 뒤 검색 화면의 키보드를 다시 띄워 주지 않는 변경이고, 다른 하나는 Crashlytics에 잡히지 않는 새로운 종류의 프로세스 종료다. 둘 다 내가 읽지 않은 페이지에 있었다.

## 7월 점검의 범위

안드로이드는 버전마다 동작 변경 문서를 두 페이지로 나눠 둔다. [Behavior changes: apps targeting Android 17](https://developer.android.com/about/versions/17/behavior-changes-17)은 `targetSdk`를 37로 올릴 때 옵트인하는 변경을 모은 페이지다. 반면 [Behavior changes: all apps](https://developer.android.com/about/versions/17/behavior-changes-all)에는 `targetSdk`가 무엇이든 안드로이드 17에서 실행되는 모든 앱에 플랫폼이 적용하는 변경이 있다.

이 앱은 Compose Multiplatform으로 만든 퀴즈 앱으로, 코드베이스 하나로 안드로이드 앱 네 개를 배포하고 `minSdk`는 28이다. 7월 31일에 타겟 페이지를 항목별로 코드와 맞춰 봤는데, 그때 목록은 15개였고 코드를 고쳐야 할 항목은 없었다. 오디오, 연락처, 블루투스, SMS, 리플렉션, 로컬 네트워크는 하나도 쓰지 않는다. 화면 방향 제한도 선언하지 않았고, AGP와 Play Billing 버전은 이미 요구 버전보다 높았다. 정작 손볼 것은 대화면에서 방향이 자유로워지면 더 자주 드러날 기존 버그 몇 개였다. 예를 들어 퀴즈 타이머 상태를 그냥 `remember`에 들고 있어서 회전 한 번에 날아가는 버그가 있었다.

그래서 마이그레이션은 두 단계로 나누고 결정 기록에 남겼다. `compileSdk`는 API 표면만 넓히므로 바로 37로 올렸다. `targetSdk`는 기록에 '연중 가장 바쁜 구간'이라고 적은 시기가 지나면 올리기로 했다. 스테이징 환경이 없어서 모든 배포가 곧 운영이고, 사용자도 바로 업데이트하지 않기 때문이다. 이렇게 나눈 대가는 린트 경고 `OldTargetApi` 하나였다.

## 8월이 바쁘다는 잘못된 전제

8월 21일에 남은 단계를 끝내려고 돌아와서 전제부터 다시 확인했다. 알고 보니 결정 기록을 쓸 때 시험 일정을 트래픽 일정으로 잘못 읽었다. 문제의 앱이 다루는 시험은 8월에 2차가 있지만, 그 앱은 4월의 1차만 다룬다. 월별 수치를 보니 정점은 4월이었고, 8월은 사용자가 있는 달 가운데 가장 조용했다.

그 사이 같은 주장이 문서와 에이전트 스킬, 메모 열세 곳에 퍼져 있었고, 상관없는 스토어 등록 정보 배포까지 그 주장에 묶여 있었다. 예전 기록은 고치지 않고 그것을 대체하는 결정 기록을 새로 썼다. 그리고 예전 기록 맨 위에 전제가 틀렸다고 표시해 다시 인용되지 않게 했다.

꽤 민망했는데, 더 큰 구멍은 공식 페이지를 다시 읽다가 나왔다.

## targetSdk와 상관없이 적용되는 아홉 항목

all-apps 페이지는 `targetSdk`와 상관없이 적용된다. 즉, 안전하다고 골라 둔 `targetSdk` 36에서도 앱은 처음부터 내가 생각한 안드로이드 16 동작 그대로가 아니었다. 이 페이지도 타겟 페이지와 같은 방식으로 훑었고, 8월 21일 기준 항목은 아홉 개였다.

| 변경 (모든 앱, 안드로이드 17) | 이 앱에 해당 여부 | 확인 방법 |
|---|---|---|
| 앱이 처리하지 않은 구성 변경 뒤 IME 표시 상태가 복원되지 않음 | 해당 | `windowSoftInputMode` 선언 없음, 검색 화면이 복원에 의존하고 있었음 |
| 기기 RAM 기반 앱 메모리 한도 | 해당 | 어느 앱이든 종료될 수 있고, 그 종료는 크래시가 아님 |
| 암묵적 URI 권한 부여 제한 | 해당 없음 | `ACTION_SEND`·`ACTION_SEND_MULTIPLE`·`ACTION_IMAGE_CAPTURE`·`FileProvider` 없음, 강제 적용은 안드로이드 18부터 |
| 앱별 Keystore 키 개수 한도 | 해당 없음 | `KeyStore`·암호화 preferences 사용 없음 |
| SMS OTP 보호(전달 지연, WebOTP까지 확대) | 해당 없음 | SMS 사용 없음 |
| 프로필 간 loopback 차단 | 해당 없음 | loopback 통신 없음 |
| pointer capture 중 터치패드 상대 이벤트 | 해당 없음 | `requestPointerCapture` 없음 |
| 백그라운드 오디오 강화 | 해당 없음 | 오디오 API 없음 |
| 블루투스 자동 재페어링 | 해당 없음 | 블루투스 사용 없음 |

10월 31일에 다시 열어 보니 항목이 열 개로 늘어 있었다. 새로 생긴 하나는 `usesCleartextTraffic` 지원 중단 계획이고, 같은 기간에 타겟 페이지도 15개에서 17개가 됐다.

## 회전 뒤 검색 화면 키보드

all-apps 페이지의 해당 문장은 다음과 같다. "Beginning with Android 17, when the device's configuration changes (for example, through rotation), and this is not handled by the app itself, the previous IME visibility is not restored." 즉, 구성 변경 뒤에도 키보드가 필요하면 앱이 직접 요청해야 한다. 방법은 `android:windowSoftInputMode="stateAlwaysVisible"`을 선언하거나 코드에서 요청하는 것이다.

검색 화면은 진입 전환이 끝나면 입력 필드에 한 번 자동으로 포커스를 주고 키보드를 연다. 자동 포커스를 이미 했다는 사실은 `rememberSaveable` 플래그에 담았는데, 키보드를 일부러 닫은 사람에게 회전 한 번으로 키보드를 다시 띄우지 않으려고 넣은 플래그다. 안드로이드 17 이전에는 플래그가 회전 뒤에도 유지되어 화면이 의도대로 포커스를 다시 요청하지 않았고, 키보드를 열어 두었던 사람에게는 시스템이 알아서 키보드를 복원해 줬다. 하지만 안드로이드 17에서는 시스템이 이 복원을 하지 않으므로, 그대로 두면 회전할 때마다 키보드를 열어 둔 사람까지 키보드를 잃게 된다.

알고 보니 플래그 하나에 두 가지 의미가 섞여 있었다. 자동 포커스를 이미 했는지, 그리고 필드에 포커스가 있었는지다. 둘을 분리하고, 복원 여부는 두 번째 값만 보고 정하게 했다.

```kotlin
var hasAutoFocused by rememberSaveable { mutableStateOf(false) }
var hadFocus by rememberSaveable { mutableStateOf(false) }
// 한 번만 읽는다: '지금 포커스가 있나'가 아니라 '이 컴포지션이 포커스 상태로 시작했나'
val restoreFocus = remember { hadFocus }

LaunchedEffect(transitionSettled) {
    if (!transitionSettled) return@LaunchedEffect
    if ((autoFocus && !hasAutoFocused) || restoreFocus) {
        hasAutoFocused = true
        focusRequester.requestFocus()
        keyboardController?.show()
    }
}

SearchField(
    focusRequester = focusRequester,
    onFocusChange = { focused -> hadFocus = focused },
)
```

내가 틀리기 쉬웠던 줄은 `remember { hadFocus }`다. `LaunchedEffect` 블록이 실시간 `hadFocus`를 읽으면 키보드를 닫는 순간 `false`가 되고 포커스를 주면 다시 `true`가 되므로, 포커스가 바뀔 때마다 조건을 다시 따지게 된다. 진입할 때 한 번만 읽으면 이 값은 직전 구성의 상태를 나타내는 값으로 고정된다.

더 간단히 고치는 방법도 두 가지 있었다. `hasAutoFocused`를 그냥 `remember`로 되돌리면 단어 하나로 끝나지만, 키보드를 닫은 사람에게 다시 열지 않는다는 원래 의도가 사라진다. 매니페스트에 `stateAlwaysVisible`을 선언하면 검색 화면뿐 아니라 앱의 모든 화면이 영향을 받는다. 플래그를 나누는 쪽은 수정이 복원에 의존하던 화면 하나 안에서 끝나므로 이 방법을 골랐다.

10월에는 이와 상관없는 레이아웃 문제 때문에 메인 액티비티가 화면 방향과 창 크기 변경을 직접 처리하도록 바꿨다. 이제 회전으로는 액티비티가 다시 만들어지지 않아 이 경로를 타지 않는다. 다크 모드나 글꼴 크기, 언어를 바꾸면 여전히 다시 만들어지는데, 그때는 이번 수정 덕분에 키보드가 유지된다.

## 종료 이력으로 메모리 한도 종료 감지하기

두 번째 변경은 이 문장이다. "Android 17 introduces app memory limits based on the device's total RAM." 한도를 넘은 앱은 나중에 프로세스 종료 이력에 나타나고, 페이지도 그 이력을 확인하라고 안내한다. 이 종료는 크래시가 아니라 시스템이 프로세스를 죽이는 것이다. 앱 안에서 이를 알아챌 코드가 실행 중일 수 없으므로 Crashlytics에도 보고가 가지 않는다. 사용자 눈에는 앱이 그냥 사라지고, 다음 실행은 콜드 스타트가 된다.

남는 기록은 종료 이력뿐이고, 그마저도 지나고 나서야 읽을 수 있다. 무엇을 찾아야 하는지는 페이지에 나와 있다. "the exit reason will be `REASON_OTHER` and the description will contain the string `"MemoryLimiter:AnonSwap"`." 그래서 앱이 실행될 때마다 이력을 읽고, 새로 생긴 메모리 한도 종료를 분석 이벤트로 남기게 했다. 판정 로직은 유닛 테스트를 붙일 수 있게 공통 코드에 두고, 플랫폼 API를 읽는 부분만 간단한 안드로이드 함수로 감쌌다. 코드는 다음과 같다.

```kotlin
fun reportMemoryLimitKills(context: Context, prefs: SharedPreferences) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return  // API 30+
    val am = context.getSystemService(ActivityManager::class.java) ?: return
    val since = prefs.getLong("watermark", 0L)
    val exits = am.getHistoricalProcessExitReasons(null, 0, 32)

    exits.filter { it.timestamp > since && it.description?.contains("MemoryLimiter") == true }
        .sortedBy { it.timestamp }
        .forEach { log("app_exit_memory_limit", it.description.orEmpty().take(100)) }

    // 종료 종류와 상관없이 본 것 전부를 넘기고 뒤로는 절대 가지 않는다.
    val newest = exits.maxOfOrNull { it.timestamp } ?: since
    prefs.edit().putLong("watermark", maxOf(since, newest)).apply()
}
```

가장 오래 고민한 부분은 워터마크를 옮기는 방식이다. 이력에는 최근 프로세스 종료가 전부 들어 있는데, 거의 다 사용자가 앱을 스와이프해서 닫은 것 같은 일반적인 종료다. 메모리 한도 종료가 있을 때만 워터마크를 옮기면, 스와이프로만 닫히는 앱은 실행할 때마다 이력 전체를 다시 읽고 다시 분류하게 된다. 그래서 종류와 상관없이 읽은 종료를 모두 지나가도록 워터마크를 옮기고 뒤로는 되돌리지 않게 했다. 덕분에 플랫폼이 이력을 잘라 내도 이미 보고한 종료가 다시 보고되지 않는다.

이유 코드가 일반적인 `REASON_OTHER`이므로 판정은 설명 문자열로 한다. 이 코드는 의존성 주입 컨테이너가 생기기 전인 `Application.onCreate`에서 실행되기 때문에, 워터마크는 별도 `SharedPreferences` 파일에 둔다. 읽기는 `Dispatchers.IO`에서 돌리고 결과를 기다리지 않는다. 프로세스 시작 시점의 바인더 호출이라 실패하더라도 진단 하나가 빠질 뿐 앱은 그대로 실행된다. 판정, 워터마크 이동, 이력 잘림, 100자 절단은 유닛 테스트 16개로 고정했다.

10월 31일에 다시 읽은 all-apps 페이지에는 `adb shell am memory-limiter`로 한도를 직접 걸어 보는 방법도 나와 있다. `manual <pid> <limit>` 모드와 `status` 하위 명령이 있다.

## 안드로이드 17 사용자가 0명일 때 targetSdk 올리기

두 변경을 고친 뒤 남은 건 `targetSdk`를 언제 올리느냐였다. 최근 14일 분석 데이터에서 안드로이드 17 사용자는 앱 네 개 모두 0명이었고, 가장 높은 버전은 안드로이드 16이었다. 두 페이지의 변경이 아직 아무에게도 적용되지 않았으므로, 그 주에 옵트인하는 비용이 가장 낮았다.

저장소의 `targetSdk`를 바꾸는 것만으로는 사용자에게 아무것도 배포되지 않는다. 그래서 37로 올리고, 대화면 수동 테스트는 다음 스토어 배포의 선행 조건으로 남겼다. 수동 단계 하나 때문에 SDK 업그레이드 전체가 기약 없이 멈춰 있는 건 피하고 싶었다.

## 두 번째 점검 전후 비교

| | 7월 31일(타겟 페이지만) | 8월 21일(두 페이지) |
|---|---|---|
| 검토한 동작 변경 | 15 | 15 + 9 |
| 이 앱에서 코드 수정이 필요한 변경 | 0 | 2 (둘 다 all-apps 페이지) |
| `targetSdk` | 36 | 37 |
| 린트 이슈 | 1 (`OldTargetApi`) | 0 |
| 호스트 테스트 | 358 | 495, 실패 0 |

3주 동안 다른 작업으로도 테스트가 늘었다. 리포터를 두는 비용은 이벤트 정의 하나와 실행당 바인더 호출 한 번이다.

## 정리

바쁜 시기라는 전제는 내가 월별 수치를 들여다보기 전까지 열세 곳에 복사되어 있었다. '시즌이 끝나면' 같은 문장은 결정 기록에 한번 들어가면 쓴 나조차 다시 확인하지 않았다.

7월 점검은 꼼꼼했고, 스스로 던진 질문인 'targetSdk를 올리면 무엇이 바뀌나'에는 제대로 답했다. 하지만 사용자가 새 OS를 설치하면 무엇이 바뀌는지는 묻지 않았다. 그 질문을 다루는 페이지는 따로 있고, 거기 실린 변경은 옵트아웃도 없이 사용자에게 먼저 적용된다. 지금은 플랫폼 마이그레이션을 페이지마다 하나씩, 읽은 날짜를 붙인 점검 두 개로 진행한다. 두 페이지 모두 출시 뒤에도 계속 바뀌었기 때문이다. all-apps 점검표는 모든 행이 '해당 없음'이어도 적어 둔다. '해당 없음' 아홉 줄이 그 페이지를 읽었다는 증거다.
