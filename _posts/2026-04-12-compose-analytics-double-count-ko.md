---
title: "버튼 하나로만 열리는데 탭 118번에 노출 144번이 찍힌 Compose 다이얼로그"
description: "버튼 하나로만 열리는 페이월 다이얼로그가 탭 118번에 노출 144번으로 기록됐다. 노출 로그를 컴포저블 본문에서 남겨 리컴포지션이 일어날 때마다 다시 찍힌 것이 원인이었다."
date: 2026-04-12 13:05:38 +0900
categories: [Android]
tags: [compose, analytics, recomposition, bigquery, firebase]
lang: ko-KR
hidden: true
mermaid: false
ref: compose-analytics-double-count
permalink: /ko/posts/compose-analytics-double-count/
math: false
---

BigQuery 내보내기를 보니 프리미엄 배너 클릭은 118번인데 페이월 노출은 144번이었다. 홈 화면에서 페이월 다이얼로그를 여는 방법은 그 배너를 누르는 것 하나뿐이므로, 구매 퍼널의 뒤 단계가 앞 단계보다 커져 있었다. 두 이벤트의 고유 사용자 수가 같았으므로 같은 사람을 여러 번 세고 있었고, 원인은 컴포저블 안에 잘못 둔 로그 한 줄이었다.

## 배너에서 구매까지의 이벤트

이 앱은 Compose Multiplatform으로 만든 퀴즈 앱이고, 한 번 사면 끝나는 유료 상품이 있다. 코드베이스 하나를 product flavor로 나눠 퀴즈 앱 여러 개를 내는데, 7월에는 네 개였다. 홈 화면에서 구매까지는 이벤트 세 개가 이어지며, Firebase Analytics로 기록하고 BigQuery 내보내기에서 읽는다.

```
iap_banner_click  ->  paywall_shown  ->  iap_purchase_click  ->  iap_purchase_success
   (배너 탭)          (다이얼로그 열림)     (구매 탭)               (스토어 확인)
```

설정 화면에도 같은 배너와 다이얼로그가 있고 `referer = "settings"`로 구분한다. 해설 잠금을 푸는 세 번째 경로는 다이얼로그를 거치지 않고 바로 스토어로 간다.

처음 두 단계 사이에는 다른 경로가 없다. 배너를 누르면 플래그가 켜지고, 플래그가 켜지면 다이얼로그가 뜬다. 두 이벤트 모두 홈 화면에서 기록되고 `iap_banner_click`을 남기는 클릭 핸들러가 플래그를 켜는 유일한 곳이므로, `banner_click`과 `paywall_shown`은 같아야 한다.

## 같은 사용자에게서 나온 노출 26번

홈 경로만 떼어 보면 내보내기 수치는 이랬다.

| 이벤트 | 횟수 | 관계 |
|---|---|---|
| `iap_banner_click` | 118 | |
| `paywall_shown` | 144 | 클릭보다 26번 많음, +22% |
| 두 이벤트의 고유 사용자 | 같음 | 같은 사람들 |

진입 경로가 하나뿐인 단계가 22% 더 크다면, 다이얼로그가 한 번 열릴 때 두 번째 이벤트가 여러 번 찍힌다는 뜻이다. 늘어난 횟수가 다른 사람에게서 나왔다면 고유 사용자 수가 달랐을 텐데 둘은 같았다. 따라서 내가 모르는 진입 경로를 찾을 필요는 없었고, 같은 사용자가 노출 로그를 여러 번 남긴다고 보고 코드를 열었다.

## 컴포저블 본문 안의 logEvent

노출 이벤트는 다이얼로그를 띄우는 `if` 안, 즉 컴포저블 본문에서 바로 기록되고 있었다.

```kotlin
var showPaywall by rememberSaveable { mutableStateOf(false) }

if (showPaywall) {
    analytics.logEvent("paywall_shown", mapOf("referer" to "home"))  // 리컴포지션마다 실행된다
    PaywallDialog(
        onDismiss = { showPaywall = false },
        onPurchase = { /* ... */ },
    )
}
```

Compose는 트리의 그 부분에서 리컴포지션이 일어날 때마다 컴포저블 함수를 다시 실행하고, 다이얼로그가 떠 있는 동안에도 이런 일은 여러 번 생길 수 있다. 이 컴포저블이 읽는 상태가 바뀌면 본문이 다시 돌았는데, `if`는 여전히 참이었으므로 `logEvent`도 다시 불렸다. 리컴포지션이 몇 번 일어날지는 Compose가 보장하지 않으므로, 수치가 딱 두 배로 나올 이유도 없었다.

설정 화면도 자체 플래그로 같은 패턴을 쓰고 있어서 둘 다 고쳤다.

## LaunchedEffect로 로그 옮기기

노출 로그는 다이얼로그가 열릴 때 따라오는 사이드 이펙트다. 그래서 다이얼로그를 여는 값을 키로 쓰는 `LaunchedEffect` 블록으로 로그를 옮겼다.

```kotlin
LaunchedEffect(showPaywall) {
    if (showPaywall) {
        analytics.logEvent("paywall_shown", mapOf("referer" to "home"))
    }
}

if (showPaywall) {
    PaywallDialog(
        onDismiss = {
            analytics.logEvent("paywall_dismissed", mapOf("referer" to "home"))
            showPaywall = false
        },
        onPurchase = { /* ... */ },
    )
}
```

`LaunchedEffect`는 컴포지션에 들어갈 때 블록을 실행하고, 그 뒤로는 키가 바뀔 때만 다시 실행한다. `showPaywall == true`인 채로 리컴포지션이 일어나면 키가 그대로이므로 아무것도 기록하지 않고, 플래그가 `false`에서 `true`로 바뀌면 이펙트가 다시 시작되면서 한 번만 기록한다. `paywall_dismissed`와 `iap_purchase_click`은 원래부터 클릭 람다 안에 있었다. 탭 한 번에 한 번만 도는 자리라 이 버그와는 관계가 없었다.

이렇게 고쳐도 두 번 찍히는 경우가 하나 남는데, 그건 받아들였다. 플래그를 `rememberSaveable`로 들고 있으므로 다이얼로그가 떠 있는 동안 액티비티가 다시 만들어지면 플래그가 `true`로 복원되고, 이펙트가 컴포지션에 다시 들어가며 노출을 한 번 더 남긴다. 그래도 리컴포지션마다 한 번이던 것이 재생성마다 한 번으로 줄어든다. 사용자 눈에도 다이얼로그가 다시 나타나므로 실제 두 번째 노출로 볼 여지도 있다. 열 때마다 정확히 한 번만 기록해야 한다면 '이미 기록함' 표시도 플래그와 함께 저장 상태로 두면 된다.

## 진입 경로별 퍼널 분리

같은 커밋에서 퍼널을 읽는 방식도 바꿨다. 홈, 설정, 해설 잠금 해제는 전환 양상이 서로 다르고, 마지막 경로는 다이얼로그를 아예 지나지 않는다. 셋을 한 퍼널에 섞어 두면 어떤 숫자가 어느 경로의 것인지 알 수 없으므로 리포트 쿼리를 `referer` 파라미터별로 나눴다.

```sql
SELECT
  event_name,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'referer') AS referer,
  COUNT(*) AS events,
  COUNT(DISTINCT user_pseudo_id) AS users
FROM `my-project.analytics_XXXX.events_*`
WHERE _TABLE_SUFFIX BETWEEN
    FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE('Asia/Seoul'), INTERVAL 30 DAY))
    AND FORMAT_DATE('%Y%m%d', CURRENT_DATE('Asia/Seoul'))
  AND event_name IN ('iap_banner_click', 'paywall_shown', 'paywall_dismissed',
                     'iap_purchase_click', 'iap_purchase_success')
GROUP BY event_name, referer
ORDER BY referer, event_name
```

전체 이벤트 수와 고유 사용자 수를 나란히 놓고 보다가 중복을 찾았으므로, 쿼리에도 이벤트마다 두 열을 모두 남겼다.

그런데 이렇게 나눈 탓에 7월에는 다른 실수가 나왔다. 한 리포트가 그룹별 `COUNT(DISTINCT user_pseudo_id)`를 더해서 합계를 냈는데, 같은 사용자가 여러 referer·에러 유형 그룹에 걸쳐 나오므로 합이 실제 인원보다 컸다. 그룹 없이 다시 돌리자 4명이던 수치가 2명이 됐다. 그때 규칙을 하나 적어 뒀다. 합계는 `GROUP BY` 없는 별도 쿼리로 내고, 그룹 값을 더해서 만들지 않는다.

## 7월 확인 결과 1 : 1

| 측정 | `banner_click` : `paywall_shown` |
|---|---|
| 수정 전, 홈 경로(4월) | 118 : 144 |
| 수정 후, 최근 30일(7월, 앱 네 개) | 모든 앱에서 1 : 1 |

7월 확인은 최근 30일 BigQuery 데이터로 돌리는 정기 퍼널 점검에서 했다. 그때 두 이벤트를 구조상 같은 단계로 보고, 퍼널의 그 구간을 병목 후보에서 뺐다. 노출 수가 부풀어 있던 동안에는 클릭에서 노출로 가는 단계가 들여다볼 구간처럼 보였으므로, 그 구간을 후보에서 뺄 수 있었던 것만으로도 의미가 있었다.

## 진입 경로가 하나뿐인 단계에 넣을 검사

요즘 Compose에서는 화면에 나타날 때 한 번만 일어나야 할 일을 표시 여부를 나타내는 값을 키로 한 이펙트에 넣고, 컴포저블 본문에는 화면에 그릴 것만 둔다. 로그는 잘못 둬도 눈에 보이는 문제가 생기지 않아서 이런 실수를 놓치기 쉽다. UI는 그대로였고, 틀린 숫자도 그것만 봐서는 그럴듯했다.

이번 버그는 진입 경로가 하나뿐인데도 앞 단계보다 큰 퍼널 단계와, 전체 이벤트 수 옆에 둔 고유 사용자 열 덕분에 잡을 수 있었다. 다음에 퍼널을 만들 때는 이 검사를 처음부터 넣을 생각이다. N단계가 N-1단계에서만 도달 가능하다면 N이 더 크지 않은지 보고, 더 크면 사용자당 이벤트 수부터 확인한다.
