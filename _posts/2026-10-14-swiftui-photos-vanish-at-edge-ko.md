---
title: "48MB 썸네일을 고친 탓에 SwiftUI 격자 버그를 11주 동안 못 봤다"
description: "SwiftUI 채팅에서 말풍선이 화면 끝에 닿으면 사진이 전부 사라졌다. 7월에는 다운샘플로 고쳤고 10월에는 뒤집힌 리스트 속 LazyVGrid가 원인이었다."
date: 2026-10-14 20:18:00 +0900
categories: [iOS]
tags: [swiftui, imageio, lazyvgrid, gpu-memory, image-loading]
lang: ko-KR
hidden: true
mermaid: false
ref: swiftui-photos-vanish-at-edge
permalink: /ko/posts/swiftui-photos-vanish-at-edge/
math: false
---

내 SwiftUI 채팅 앱에서는 사진 말풍선이 화면 위나 아래 끝에 1픽셀만 걸쳐도 화면의 사진이 한꺼번에 사라졌다. 실제 아이폰에서만 그랬다. 7월에 열 시간 사이 수정을 세 번 내보냈고 세 번째 수정을 원인으로 노트에 적었다. 썸네일을 원본 해상도로 디코드해서 한 장이 48MB쯤 됐다는 내용이다.

10월에 같은 증상이 돌아왔다. 이번 원인은 노트에서 아니라고 지워 둔 쪽이었다. 지연 격자가 뒤집힌 좌표로 계산하다가 가장자리 타일을 화면 밖으로 판단했다.

## 뒤집힌 리스트 안의 사진 격자

작은 비공개 채팅 앱이고 iOS 26을 대상으로 Swift 6과 SwiftUI로 만든다. 타임라인은 흔히 쓰는 뒤집힌 리스트 기법이다. 최신 메시지가 아래에 오고 새 메시지가 와도 스크롤 위치가 밀리지 않는다.

```swift
ScrollView {
    LazyVStack {
        ForEach(messages.reversed()) { message in
            MessageRow(message)
                .scaleEffect(x: 1, y: -1)   // 행은 다시 뒤집는다
        }
    }
}
.scaleEffect(x: 1, y: -1)                   // 리스트 전체를 뒤집는다
```

사진 메시지는 타일 1~10개가 든 말풍선이다. 타일은 한 칸 또는 두 칸짜리 `LazyVGrid`로 배치했고 각 타일은 둥근 클립 안에 `scaledToFill`로 이미지를 그렸다.

사진 말풍선이 화면 밖으로 조금 나갈 때까지 스크롤하면 걸친 타일만이 아니라 화면의 사진 타일 전부가 비었다. 글 말풍선은 멀쩡했다. 시뮬레이터에서는 한 번도 나오지 않았다.

## 열 시간 동안 세 번 고치기

세 커밋 모두 같은 날 01:09부터 11:07 사이에 있다.

| 커밋 시각 | 가설 | 바꾼 것 | 실기기 결과 |
|---|---|---|---|
| 01:09 | 변환된 부모가 일부만 자르면 `scaledToFill`이 넘쳐 그린 레이어가 통째로 빠진다 | 이미지에 `.clipped()` | 여전히 사라짐 |
| 10:31 | 행 변환 아래에서 SwiftUI가 이미지 레이어를 통째로 컬링한다 | 타일을 `.drawingGroup()`으로 평탄화 | 여전히 사라짐 |
| 11:07 | 원본 해상도 디코드가 GPU 텍스처 예산을 넘긴다 | ImageIO로 다운샘플, 긴 변 1600px | 수정으로 내보냄 |

앞의 두 가설은 렌더링 쪽이었다. 시뮬레이터에서는 문제가 아예 안 나니 어느 쪽도 확인할 수 없었다. 나는 그걸 힌트로 받아들였다. 하드웨어에서만 깨진다면 하드웨어에 모자란 자원이 있을 거라고 생각했다. 그 생각으로 디코드 문제를 찾았고 같은 생각 때문에 거기서 멈췄다.

## 카메라 사진 한 장에 48.8MB

세 번째 가설은 어떤 사진이 깨지는지 보다가 나왔다. 작은 이미지는 괜찮았고 카메라로 찍은 사진만 문제였다. 썸네일 로더가 원본 파일에 `UIImage(data:)`를 불렀으니 1200만 화소 사진은 4032 × 3024 비트맵이 됐다.

| 디코드 | 화소 | 4바이트/화소 기준 크기 |
|---|---|---|
| 원본 4032 × 3024 | 12.2M | 48.8MB |
| 긴 변 1600 (1600 × 1200) | 1.92M | 7.7MB |
| 긴 변 1200 (1200 × 900), 10월 | 1.08M | 4.3MB |

사진 말풍선 몇 개가 뜬 화면이면 원본 해상도 텍스처만 수백 MB다. 그때 내 설명은 이랬다. 행이 가장자리를 넘어 다시 합성되면 GPU가 자리를 만들려고 텍스처를 내보내는데 그때 전부를 내보낸다.

ImageIO로 다운샘플했다.

```swift
import ImageIO
import UIKit

func thumbnail(from data: Data, maxPixel: CGFloat) -> UIImage? {
    guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,   // 작은 내장 썸네일은 무시
        kCGImageSourceCreateThumbnailWithTransform: true,     // EXIF 방향 반영
        kCGImageSourceShouldCacheImmediately: true,           // 처음 그릴 때가 아니라 지금 디코드
        kCGImageSourceThumbnailMaxPixelSize: maxPixel,
    ]
    return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
        .map(UIImage.init(cgImage:))
}
```

전체 화면 뷰어는 원본을 디코드하는 경로를 따로 남겼다. 사진을 누르면 여전히 원본 화질로 보인다. gotchas 파일에는 "오진: 컬링·변환, 원인: 디코드 크기"라고 적었다. 두 번째 시도에서 넣은 `.drawingGroup()`은 코드에 그대로 남았다.

## 10월에 다시 빈 타일

10월에는 끌어내려 닫는 사진 뷰어와 디스크 캐시를 만들고 있었다. 그러다 사진 말풍선이 다시 가장자리에서 사라졌다. 관련된 두 파일은 7월 이후 색상 개편 말고는 바뀐 게 없었다. 7월 수정이 처음부터 모자랐거나 새로 만든 무언가가 큰 이미지를 화면에 다시 올렸거나 둘 중 하나였다. 답은 둘 다였다.

새로 생긴 쪽은 뷰어였다. 뷰어는 원본을 디코드해서 썸네일과 같은 메모리 캐시에 같은 URL 키로 넣었다. 사진을 열었다 닫으면 말풍선 타일이 자기 URL로 캐시를 찾다가 1200만 화소 이미지를 받았다. 7월의 다운샘플은 여전히 돌았지만 캐시에 없을 때만 돌았다.

처음부터 있던 쪽은 격자였다. 그날 커밋 메시지에 원인을 이렇게 적었다. 뒤집힌 지연 리스트 안의 `LazyVGrid`가 보이는 영역을 뒤집힌 좌표로 계산했다. 그래서 말풍선이 화면 끝에 닿는 순간 타일을 화면 밖으로 보고 내려 버렸다.

## 즉시 격자와 캐시 둘

지연 격자를 걷어내고 캐시를 나눴다.

```swift
// 1. 즉시 격자. 타일은 많아야 10개라 매번 만들어도 싸다.
Grid(horizontalSpacing: 4, verticalSpacing: 4) {
    ForEach(rows, id: \.first?.id) { row in        // 미디어를 1~2개씩 줄로 끊는다
        GridRow {
            ForEach(row) { item in Tile(item) }
            if row.count < columns {
                Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
            }
        }
    }
}

// 2. 캐시를 나눠 썸네일 조회가 원본을 돌려줄 수 없게 한다.
let thumbnailCache = ImageCache(costLimit: 80 * 1024 * 1024)
let fullSizeCache  = ImageCache(costLimit: 150 * 1024 * 1024)
```

세 번째로 썸네일 상한을 1600px에서 1200px로 낮췄다. 1600은 화면 폭을 꽉 채우는 타일에 맞춘 값이었다. 타일 하나짜리 말풍선은 폭이 260pt쯤이고 3배율이면 780px다. 1200이어도 여유가 있고 타일당 크기는 7.7MB에서 4.3MB로 거의 절반이 된다.

## 메인 액터에 묶인 디코더

그 커밋 38분 뒤 같은 빌드에서 회귀를 하나 더 고쳤다. 사진 말풍선이 많은 대화에 들어가면 화면이 굳고 터치가 씹혔다. 로더는 떼어 낸 작업에서 디코더를 불렀다. 그런데 프로젝트의 기본 격리가 `MainActor`라서 내가 어디에도 쓰지 않았는데 디코더 타입이 메인 액터에 묶여 있었다. 다운샘플할 때마다 메인 스레드로 건너간 셈이다. 디코더에 `nonisolated`를 붙이고 말풍선 썸네일 작업의 우선순위를 `.utility`로 내렸다. 이제 스크롤과 탭보다 뒤에 돈다.

## 475줄을 Nuke로 바꾸기

10월 말에는 이미지 코드가 꽤 불어나 있었다. 디스크 캐시가 있었고 같은 요청을 합치고 화면을 벗어난 타일의 작업을 끊는 다운로더가 있었다. 메모리 캐시 둘과 ImageIO 디코더도 있었다. 이걸 전부 Nuke 13으로 바꿨다. Nuke 파이프라인은 원본과 축소본을 디스크와 메모리에 캐시하고 요청 합치기와 취소, ImageIO 다운샘플까지 맡는다. 가장 많이 바뀐 iOS 미디어 파일 네 개에서 내 코드 약 475줄이 빠졌고 181줄짜리 래퍼가 들어갔다. Nuke 메이저 버전을 따라가야 하고 업데이트 뒤 모든 사진을 한 번 다시 받아야 한다. 둘 다 감수하기로 했다.

## 7월 노트에 적었어야 할 것

어느 수정보다 7월 노트가 비쌌다. 진짜 원인 하나를 찾고 그걸 원인이라고 적었다. 그 뒤로 그 항목은 나에게도, 같이 일하는 코딩 에이전트들에게도 컬링은 보지 말라고 했다. 시뮬레이터가 재현조차 못 했으니 시뮬레이터에서 멀쩡했다는 건 근거가 될 수 없었다.

지금은 gotchas 항목을 두 줄로 나눠 쓴다. 무엇이 증상을 고쳤는지, 그리고 다른 용의자를 무슨 근거로 지웠는지다. 이 버그에서 챙긴 확인도 하나 있다. 작은 이미지는 되는데 큰 이미지만 하드웨어에서 깨지면 레이아웃보다 디코드 크기와 메모리를 먼저 본다. 크기가 다른 이미지에는 캐시 키도 따로 준다. Nuke는 축소본을 크기별 키로 나누기 때문에 어느 경로가 먼저 캐시를 채웠든 썸네일 조회가 원본을 받아 올 일이 없다.
