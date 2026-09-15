---
title: "호스트 앱 없이 찍은 SwiftUI 스냅샷에는 커서와 AsyncImage가 없다"
description: "호스트 앱 없이 swift-snapshot-testing으로 SwiftUI 상태를 시안 크기 PNG로 뽑아 봤다. 그려지는 것과 빠지는 것, 빠진 것을 상태로 그린 방법을 정리했다."
date: 2026-09-15 15:52:55 +0900
categories: [iOS]
tags: [swiftui, snapshot-testing, ios, testing, xctest]
lang: ko-KR
hidden: true
mermaid: true
ref: swiftui-snapshot-without-app-gaps
permalink: /ko/posts/swiftui-snapshot-without-app-gaps/
math: false
---

앱 없이 유닛 테스트로 그린 `TextField`는 포커스를 줘도 커서가 없다. 로컬 파일을 가리키는 `AsyncImage`는 1초를 기다려도 자리표시만 보인다. 그런데도 테스트는 통과한다. 그림에서 빠질 뿐이다.

iOS에서도 Android에서처럼 시안 비교용 스크린샷을 뽑을 수 있는지 보다가 이 둘을 만났다. 답은 대체로 반가웠다. 적어 둘 만한 건 이 둘과 비슷한 몇 가지였다.

## 상태 값을 넣고 PNG를 받는다

Android에서는 Compose 프리뷰를 JVM에서 Roborazzi로 PNG로 그린다. 크기와 밀도를 시안 프레임에 맞추고 시안과 비교한다. 기기도 앱 실행도 필요 없다. iOS에서도 그렇게 하고 싶었다. 화면 하나에 특정 상태(빈 상태, 포커스 잡고 입력 중, 긴 본문, 600pt 스크롤, 다크 모드)를 넣으면 앱을 빌드하거나 실행하지 않고도 시안 크기 PNG가 나와야 한다.

작은 샘플을 만들어 확인했다. 샘플은 값 타입 상태 하나로만 움직이는 SwiftUI 글 작성 화면 하나와 [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing) 1.19.4를 쓰는 유닛 테스트 번들로 이뤄져 있다. 테스트는 iOS 26.5 시뮬레이터에서 `xcodebuild test`로 돌렸다. 테스트 타깃에는 호스트 앱이 없다(`TEST_HOST`를 설정하지 않았다). 테스트 타깃이 화면 소스 파일을 직접 컴파일하니 앱 타깃은 테스트에 들어가지도 실행되지도 않는다.

```mermaid
flowchart LR
  S["상태 값<br/>(모드, 텍스트, 포커스, 스크롤 오프셋)"] --> V[SwiftUI 뷰]
  V --> R["assertSnapshot<br/>오프스크린 렌더"]
  R --> P["393x852pt @3x PNG<br/>1179x2556px"]
  P --> D[시안 프레임과 비교]
```

상태 타입은 프리뷰에서도 그대로 쓰는 평범한 데이터다. 테스트는 이 값을 화면에 넘겨 찍기만 한다.

```swift
struct EditorState: Equatable {
    var title: String
    var body: String
    var isBodyFocused: Bool
    var scrollOffsetY: CGFloat = 0
    var expandsScrollContent = false   // render without ScrollView (see below)
}

final class EditorSnapshotTests: XCTestCase {
    private let frame = SwiftUISnapshotLayout.fixed(width: 393, height: 852)

    func test_typingWithFocus() {
        assertSnapshot(of: EditorScreen(state: .typingFocused), as: .image(layout: frame))
    }
}
```

## 스크롤 위치, 다크 모드, 글꼴은 됐다

Android 쪽에서 기대던 기능은 상태로 표현하기만 하면 대부분 iOS에서도 됐다. 왼쪽이 필요한 것이고 오른쪽이 iOS에서 쓴 방법이다.

| 필요한 것 | iOS에서 한 방법 |
|---|---|
| 모드, 텍스트, 선택 탭, 첨부 주입 | 상태 값을 뷰에 넘김 |
| 포커스 표시 | 상태 플래그로 포커스 테두리를 그림 |
| 세로 스크롤 위치 | `ScrollPosition(point:)`를 `.scrollPosition`에 바인딩 |
| 가로 스크롤 위치 | 같은 방식, x 오프셋 |
| 50번 항목부터 보이는 lazy 목록 | `ScrollPosition(id:)`와 `.scrollTargetLayout()` |
| 시안 프레임 크기와 밀도 | `.fixed(width:height:)`, @3x로 렌더 |
| 다크 테마 | `traits: UITraitCollection(userInterfaceStyle: .dark)` |
| 비교용 글꼴 | 번들에 넣은 글꼴을 `CTFontManagerRegisterFontsForURL(..., .process, nil)`로 등록 |

시안과 비교하려면 결과가 매번 같아야 한다. 스냅샷 테스트 19건을 다섯 번 돌렸고 이미지는 매번 똑같았다.

## 그림에서 빠진 것들

### 커서는 시스템이 그린다

`onAppear`에서 `@FocusState`를 true로 바꾼 `TextField`를 0.5초 기다렸다가 찍었다. 테두리와 글자는 나왔는데 커서가 없었다. 그래서 비교할 때는 시스템 커서에 기대지 않기로 했다. 포커스 테두리처럼 커서도 상태를 보고 직접 그린다.

```swift
struct CaretText: View {
    let text: String
    let showsCaret: Bool

    var body: some View {
        HStack(spacing: 1) {
            Text(text)
            if showsCaret {
                Rectangle().fill(Color.accentColor).frame(width: 2, height: 22)
            }
            Spacer()
        }
    }
}
```

### 1초를 기다려도 AsyncImage는 비어 있었다

`AsyncImage`는 비동기로 불러오니 바로 찍으면 `.empty` 단계가 찍힌다. 기다리면 될 줄 알았다. 그런데 `.wait(for: 1, on: .image(...))`에 파일 URL을 줘도 찍힌 건 여전히 자리표시였다. 네트워크를 거치지 않는 로컬 파일인데도 그랬다.

통한 건 Android에서 하던 방법이다. 거기서도 캡처 전에 이미지를 미리 받아 둔다. 테스트가 이미지를 먼저 읽고 `UIImage`를 상태로 넘기면 스냅샷을 찍는 동안 뷰가 비동기 단계를 거칠 일이 없다.

### 키 윈도우 렌더는 호스트 앱이 있어야 한다

swift-snapshot-testing에는 키 윈도우를 거쳐 그리는 경로(`drawHierarchyInKeyWindow: true`)도 있다. 이쪽이 더 많은 효과를 처리한다. 호스트 앱 없이 이 경로를 타면 "requires tests to be run in a host application"을 내며 크래시한다. 그래서 기본 오프스크린 렌더만 썼다. 블러처럼 실제 창이 있어야 하는 효과는 호스트 앱을 다시 붙이지 않는 한 찍을 수 없다.

### 세로로 긴 시안과 ScrollView

스크롤 화면 전체를 세로로 긴 프레임 한 장에 그린 시안도 있다. 먼저 떠오르는 두 방법을 해 봤다.

- 스냅샷 프레임을 키우면 스크롤 뷰만 길어지고 안의 내용은 똑같이 잘린다
- `.sizeThatFits`로 찍으면 `ScrollView` 높이가 0으로 줄어 본문이 사라진다

그래서 `ScrollView` 없이 내용을 펼쳐 그리는 상태 플래그를 넣었다. 이번에는 `.sizeThatFits`가 높이를 제안하지 않아 여러 줄 텍스트가 잘렸다. `UIHostingController`로 높이를 먼저 재고 그 높이로 고정해서 찍자 내용이 다 나왔다.

```swift
func test_tallFrame_fitsContent() {
    var state = EditorState.scrollAtTop
    state.expandsScrollContent = true
    let screen = EditorScreen(state: state)
    let height = UIHostingController(rootView: screen)
        .sizeThatFits(in: CGSize(width: 393, height: .greatestFiniteMagnitude))
        .height
    assertSnapshot(of: screen, as: .image(layout: .fixed(width: 393, height: height)))
}
```

샘플 화면은 높이가 2,002pt로 나왔다. 이미지로는 1179 x 6006px이다.

### 안전 영역은 되고 상태바 내용은 안 된다

시안 프레임에는 상태바와 홈 인디케이터 자리까지 들어 있다. `ViewImageConfig`에는 `safeArea`를 줄 수 있다. 393 x 852pt 프레임에 위 59pt와 아래 34pt를 주자 내용이 정확히 그만큼 안쪽으로 들어갔다. 다만 상태바 안의 시계와 배터리는 그려지지 않는다. 시안과 비교할 때는 그 띠를 가린다.

### `#Preview`는 찍을 수 없다

`#Preview` 블록은 직접 찍을 방법이 없다. 대신 프리뷰와 테스트가 같은 상태 값을 쓰게 했다. 캔버스에 보이는 그림과 테스트가 찍는 그림이 한 정의에서 나온다.

## 빠진 것과 우회 방법

| 항목 | 스냅샷에 나오나 | 우회 |
|---|---|---|
| 시스템 텍스트 커서 | 안 나옴 | 상태로 커서를 그림 |
| `AsyncImage`(1초 대기, 로컬 파일) | 자리표시만 나옴 | `UIImage`를 미리 읽어 상태로 전달 |
| 키 윈도우 렌더 | 호스트 앱 없으면 크래시 | 기본 오프스크린 렌더 |
| 블러 등 실제 창이 필요한 효과 | 안 나옴 | 호스트 앱 필요 |
| `ScrollView`를 통한 긴 프레임 | 잘리거나 높이 0 | `ScrollView` 없이 그리고 `UIHostingController`로 높이 측정 |
| 상태바 내용 | 안 나옴 | 레이아웃은 `safeArea`로, 비교할 땐 그 띠를 가림 |
| `#Preview` | 직접은 안 됨 | 프리뷰와 테스트가 상태 값을 공유 |

## 그림에 나올 것은 모두 상태로 그린다

빠진 건 모두 살아 있는 앱이라면 시스템이 대신 그려 주는 것이었다. 커서와 비동기로 불러오는 이미지가 그렇고 창 수준 효과와 상태바도 그렇다. 어느 것도 요란하게 실패하지 않았다. 테스트는 통과했고 이미지에서 한 조각이 빠졌다. 이대로 시안과 비교하면 실제 앱에는 없는 차이가 리포트에 뜬다.

그래서 스냅샷 테스트를 새로 꾸린다면 이 샘플이 끝난 자리에서 시작하겠다. 그림에 나와야 하는 건 전부 뷰가 상태를 보고 직접 그리게 한다. 프로젝트 구조에도 조건이 하나 붙는다. 앱 없이 찍으려면 화면 코드를 테스트 타깃에서 컴파일할 수 있어야 한다. 화면이 앱 모듈의 코드나 에셋에 기대고 있으면 먼저 별도 모듈로 떼어 내야 한다. iOS에서도 같은 비교를 하려는 화면이 있다면 그 화면 소스 파일을 `TEST_HOST` 없는 테스트 타깃에 넣고 컴파일부터 해 보길 권한다.
