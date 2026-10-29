---
title: "Firestore 페이지 커서 절반이 자기 문서보다 살짝 앞을 가리켰다"
description: "Double로 된 Date를 Firestore Timestamp로 되돌릴 때 소수부를 내리면 커서 절반이 저장값보다 작아진다. 마이크로초 반올림으로 고친 과정."
date: 2026-10-29 19:35:15 +0900
categories: [Kotlin Multiplatform]
tags: [firestore, swift, kotlin-multiplatform, pagination, floating-point]
lang: ko-KR
hidden: true
mermaid: false
ref: firestore-cursor-double-truncation
permalink: /ko/posts/firestore-cursor-double-truncation/
math: false
---

내 채팅 앱은 앞 페이지의 마지막 메시지로 다음 페이지 커서를 만든다. 그런데 메시지 절반쯤은 커서가 그 메시지 시각보다 1마이크로초가 채 안 되게 앞섰다. Firestore는 그 메시지를 "커서 뒤"로 보고 다음 페이지 맨 위에 또 내려보냈다. `limit(1)`이면 페이지가 아예 넘어가지 않았다.

채팅 해석 코드를 Swift에서 Kotlin Multiplatform 공유 모듈로 옮기다가 찾았다. 포팅이 만든 버그는 아니었다. Swift 코드가 7월부터 커서를 이렇게 만들고 있었다.

## Swift 브리지를 건너는 커서

작은 비공개 채팅 앱이다. iOS 클라이언트는 Firebase iOS SDK 11.15를 쓰고 공유 모듈은 Kotlin 2.4다. 검색과 기록 보기는 전체 기록 색인을 읽는데 이 색인은 메시지를 `createdAt` 오름차순으로, 같으면 문서 ID 순으로 받는다. 다음 페이지는 마지막으로 받은 메시지의 `[createdAt, id]`로 `startAfter`를 건다.

예전 메시지는 Swift 클라이언트가 `setData(from:)`로 썼다. 이 경로는 Swift `Date`를 Firestore `Timestamp`로 바꿔 저장한다. Firestore는 마이크로초까지 남기니 옛 `createdAt`에는 초 아래 여섯 자리가 있다. iOS 화면 모델은 `createdAt`을 `Date`로 들고 있고 `Date`의 실체는 초 단위 `Double`이다. 커서 값은 이 길을 지난다.

```text
Firestore          공유 Kotlin           Swift 화면 모델          다음 쿼리
createdAt   --->   (ms, nanos)   --->    Date (Double)    --->    Timestamp(seconds, nanos)
정확한 µs          정확함                가장 가까운 Double        <- 여기서 내림
                                         (오차 119 ns 이내)
```

문제는 마지막 화살표에 있었다. 여기를 찾기 전에 다른 정밀도 문제부터 고쳤다.

## 공유 타입에 밀리초 아래 값 넣기

공유 Kotlin 코드의 시각 타입은 처음에 epoch 밀리초만 담았다. 채팅 포팅 계획을 쓸 때 이미 이 위험을 적어 두었다. 커서를 밀리초로 자르면 `…123456 µs`에 저장된 메시지가 `…123000 µs` 커서보다 뒤에 놓인다. 경계 메시지가 다음 페이지에 다시 오고 `limit 1` 쿼리는 같은 메시지를 끝없이 돌려준다.

첫 커밋에서 공유 타입에 밀리초 아래 값을 담는 필드를 더했다.

```kotlin
data class Timestamp(val epochMs: Long, val nanosOfMilli: Int) {
    constructor(epochMs: Long) : this(epochMs, 0)

    val seconds: Long get() = epochMs.floorDiv(1000L)
    val nanos: Int get() = (epochMs.mod(1000L) * 1_000_000L).toInt() + nanosOfMilli

    companion object {
        fun of(seconds: Long, nanos: Int) =
            Timestamp(seconds * 1000L + nanos / 1_000_000, nanos % 1_000_000)
    }
}
```

대부분의 레코드는 지금도 밀리초만 쓰니 보조 생성자를 두어 기존 Swift 호출을 그대로 컴파일되게 했다. 공유 계약 파일에는 골든 사례 여섯 개를 넣었다. 밀리초 아래 보존·0이면 생략·음수 초·쓰기 두 건·JSON 왕복이다. 바꾸기 전에는 다섯 개가 실패했고 바꾼 뒤에는 여섯 개 모두 통과했다. Kotlin 쪽은 이걸로 맞았지만 커서는 여전히 틀렸다.

## `Timestamp(date:)`는 내림을 한다

포팅을 끝내고 리뷰를 돌리면서 브리지 건너편 Swift 코드를 다시 봤다. 다음 페이지를 요청할 때 앱은 마지막 메시지의 `Date`를 Firebase가 제공하는 생성자로 쪼갰다.

```swift
let stamp = Timestamp(date: last.createdAt)   // 소수부를 내린다
query.start(after: [stamp, last.id])
```

SDK 안에서 `Timestamp(date:)`는 `timeIntervalSince1970`에 `modf`를 걸고 `fraction * 1e9`를 `int32_t`로 캐스팅한다. 이 캐스팅이 내림이다. `Double`이 마이크로초 값을 정확히 담는다면 상관없지만 그럴 수가 없다. 1.7 × 10⁹초 근처에서 이웃한 `Double` 사이 간격은 2⁻²²초, 약 238 ns다. `dateValue()`가 만든 `Double`은 표현 가능한 가장 가까운 수라서 절반쯤은 저장된 마이크로초보다 조금 크고 나머지는 조금 작다.

크게 잡히면 내림 결과는 저장값이거나 그보다 약간 크다. 작게 잡히면 내린 뒤에도 작다. 아래는 오차가 가장 클 때의 예시 값이다.

```text
저장값           ...123456000 ns
Double (아래)    ...123455881 ns  -> 내림 커서 ...123455881 ns  <  저장값
Double (위)      ...123456119 ns  -> 내림 커서 ...123456119 ns  >= 저장값
```

`startAfter`는 `(createdAt, id)` 순서로 비교한다. 첫 번째 경우 경계 메시지의 `createdAt`이 커서보다 크니 메시지는 "커서 뒤"에 있고 다시 내려온다.

리뷰에서 무작위 저장값 10만 개를 옛 변환에 넣어 보니 50,203개가 처음 값으로 돌아오지 않았다. 같은 `Timestamp(date: cursor.createdAt)` 호출이 7월에 만든 Swift 페이지 코드에도, 포팅 닷새 전에 넣은 오름차순 구간 쿼리에도 있었다.

## 마이크로초로 반올림하기

이번 포팅에서 화면 모델의 `Date`는 그대로 두기로 했다. 그러니 `Date`를 시각 조각으로 바꾸는 변환을 정확하게 만들어야 했다. Firestore는 마이크로초까지만 저장하고 `Double` 오차는 0.5마이크로초보다 훨씬 작아서 그게 가능하다. 이 글을 쓰면서 2017~2030년 날짜로 왕복을 다시 돌려 보니 최대 오차는 119 ns였다. 가장 가까운 마이크로초로 반올림하면 저장값이 그대로 돌아온다. `Double`의 정밀도는 충분했고 값을 잃은 건 내림이었다.

```swift
enum CursorTime {
    /// 1970 기준 초 -> (epoch ms, 밀리초 아래 나노초). 마이크로초로 반올림한다.
    static func split(_ t: TimeInterval) -> (ms: Int64, nanosOfMilli: Int32) {
        var seconds = t.rounded(.down)
        var micros = ((t - seconds) * 1_000_000).rounded()
        if micros >= 1_000_000 {          // 0.9999996초는 다음 초로 올라간다
            seconds += 1
            micros -= 1_000_000
        }
        let us = Int64(micros)
        return (Int64(seconds) * 1000 + us / 1000, Int32(us % 1000) * 1000)
    }
}
```

`rounded(.down)`으로 초를 먼저 떼면 1970년 이전 날짜에서도 소수부가 음수가 되지 않는다. Firestore가 음수 초와 양수 나노초로 표현하는 방식과도 맞는다. `micros >= 1_000_000` 분기는 소수부가 반올림되어 1초가 되는 경우를 처리한다.

`Date`를 공유 시각으로 바꾸는 곳은 이제 모두 이 함수를 지난다. 페이지 커서·구간 필터·집계 개수의 경계·쓰기가 다 그렇다. 그 바람에 쓰기도 조금 달라졌다. 예전에는 나노초로 내린 값을 보내고 서버가 마이크로초로 잘랐다. 지금은 보내기 전에 마이크로초로 반올림한다. 새로 쓰는 `createdAt`은 옛 코드가 썼을 값과 1마이크로초까지 다를 수 있다. 의도한 동작 변경이라 문서에 적어 두었다.

## 10만 개로 왕복시키는 스크립트

검사는 XCTest 타깃 대신 독립 Swift 스크립트로 만들었다. `split`이 든 앱 소스 파일 하나와 함께 `swiftc`로 컴파일한다. 핵심 루프는 이렇다.

```swift
var mismatches = 0
for _ in 0..<100_000 {
    let s = Int64.random(in: 1_500_000_000...1_900_000_000)
    let us = Int64.random(in: 0..<1_000_000)
    let date = TimeInterval(s) + TimeInterval(us * 1000) * 1e-9   // dateValue()처럼
    let (ms, nanos) = CursorTime.split(date)
    if ms != s * 1000 + us / 1000 || Int64(nanos) != us % 1000 * 1000 { mismatches += 1 }
}
print("cursor-time: \(mismatches) mismatches / 100000")
exit(mismatches == 0 ? 0 : 1)
```

−0.5초와 0, −1.000001초 세 경계도 따로 본다. 하나라도 어긋나면 0이 아닌 코드로 끝난다.

| 변환 | 100,000개 중 어긋남 |
|---|---|
| `Timestamp(date:)` 내림 (이전) | 50,203 |
| 마이크로초 반올림 (이후) | 0 |

## 밀리초에서도 같은 실수

같은 날 그보다 앞서 포팅의 다른 부분을 리뷰하다가 같은 실수를 밀리초 단위에서도 찾았다. 공유 규칙은 대부분 epoch 밀리초로 도는데 브리지는 그 값을 `floor(timeIntervalSince1970 * 1000)`로 구했다. 밀리초 값으로 만든 `Date`도 1밀리초 모자라게 돌아올 수 있었다. `ms / 1000`이 `Double`로 정확하지 않아서 곱한 값이 정수 바로 아래에 떨어지기 때문이다. 리뷰에서 센 손실은 200,000개 중 1,857개였다.

일정에서 이게 문제가 됐다. 앱은 옛 시각과 새 시각을 밀리초로 비교해서 "일정 시각이 바뀌었다" 알림을 보낼지 정한다. 그래서 제목만 고쳐도 시각이 바뀐 것처럼 보일 수 있었다. 고친 코드는 내림을 유지한다. 같은 밀리초 안의 두 순간은 여전히 같게 봐야 하기 때문이다. 다만 곱한 값이 정수와 0.001 ms 안쪽으로 붙어 있으면 그 정수로 맞춘다.

```swift
var epochMillis: Int64 {
    let ms = timeIntervalSince1970 * 1000
    let nearest = ms.rounded()
    return Int64(abs(ms - nearest) < 1e-3 ? nearest : ms.rounded(.down))
}
```

이렇게 하면 밀리초 값으로 만든 `Date`는 그 밀리초로 돌아온다. 값 범위를 몇 가지로 바꿔 200,000개 표본을 다시 돌려 보니 손실은 없었다.

## 저장된 값에서 출발하는 테스트

공유 `Timestamp`가 나노초를 담게 되자 나는 커서 문제가 끝났다고 여겼다. 골든 테스트가 정수 초와 나노초에서 출발했으니 통과할 수밖에 없었다. 깨진 값은 브리지 반대편에서 `Double`을 한 번 거친 값이었고 저장값을 그 경로로 흘려보낸 테스트는 없었다. 지금은 왕복 테스트를 Firestore에 저장된 모양의 값에서 시작해서 앱이 돌아오는 길에 쓰는 표현을 전부 거치게 한다.

입력이 정확하면 내림을 써도 된다. 부동소수점을 한 번이라도 거친 값은 그 값을 저장하는 쪽의 해상도로 반올림한다. 여기서는 Firestore의 마이크로초였다. 요즘 코드를 볼 때 키·커서·같음 비교로 들어가는 `Date`·`Double` 근처에 `rounded(.down)`이나 `floor`, 정수 캐스팅이 보이면 먼저 의심한다.
