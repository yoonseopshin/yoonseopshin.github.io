---
title: "SwiftUI 사진 말풍선이 화면 끝에서 사라지는 문제"
description: "SwiftUI 채팅에서 사진 말풍선이 화면 끝에 닿으면 화면의 사진이 전부 사라졌다. 7월에는 썸네일 다운샘플링으로 고쳤는데 10월에 뒤집힌 리스트 속 LazyVGrid가 또 다른 원인으로 드러났다."
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

내 SwiftUI 채팅 앱에서 사진 말풍선이 화면 위나 아래 끝에 1픽셀만 걸쳐도 화면에 있던 사진이 한꺼번에 사라졌다. 시뮬레이터에서는 멀쩡했고 실기기에서만 그랬다. 7월에 열 시간 사이 세 번 고쳐 배포했는데, 세 번째 수정의 원인을 노트에 적어 두었다. 썸네일을 원본 해상도로 디코딩하는 바람에 한 장이 48MB쯤 됐다는 내용이다.

그런데 10월에 같은 증상이 다시 나타났다. 이번 원인은 노트에서 원인이 아니라고 지워 둔 쪽이었다. 뒤집힌 좌표로 보이는 영역을 계산하던 `LazyVGrid`가 가장자리 타일을 화면 밖에 있다고 판단하고 내려 버렸다.

## 뒤집힌 리스트 안의 사진 그리드

작은 비공개 채팅 앱이고, iOS 26을 타겟으로 Swift 6과 SwiftUI로 만들고 있다. 타임라인에는 흔히 쓰는 뒤집힌 리스트 기법을 썼다. 리스트 전체와 각 행을 한 번씩 뒤집으면 최신 메시지가 아래에 오고, 새 메시지가 와도 스크롤 위치가 밀리지 않는다.

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

사진 메시지는 타일이 1~10개 들어가는 말풍선이다. 타일은 열이 한 개나 두 개인 `LazyVGrid`로 배치했고, 각 타일은 둥근 클립 안에 `scaledToFill`로 이미지를 그렸다.

사진 말풍선이 화면 밖으로 조금 나갈 때까지 스크롤하면 걸친 타일뿐 아니라 화면에 있는 사진 타일이 전부 비었다. 글 말풍선은 그대로였고, 시뮬레이터에서는 한 번도 재현되지 않았다.

## 열 시간 동안 세 번 고치기

세 커밋 모두 같은 날 01:09부터 11:07 사이에 올렸다.

| 커밋 시각 | 가설 | 바꾼 것 | 실기기 결과 |
|---|---|---|---|
| 01:09 | 변환된 부모가 일부만 자르면 `scaledToFill`이 넘쳐 그린 레이어가 통째로 빠진다 | 이미지에 `.clipped()` | 여전히 사라짐 |
| 10:31 | 행 변환 아래에서 SwiftUI가 이미지 레이어를 통째로 컬링한다 | 타일을 `.drawingGroup()`으로 평탄화 | 여전히 사라짐 |
| 11:07 | 원본 해상도 디코딩이 GPU 텍스처 예산을 넘긴다 | ImageIO로 다운샘플링, 긴 변 1600px | 해결로 보고 배포 |

앞의 두 가설은 렌더링 쪽이었는데, 시뮬레이터에서는 문제가 아예 나지 않으니 어느 쪽도 확인할 방법이 없었다. 나는 이 점을 힌트로 보고, 실기기에서만 깨진다면 실기기 쪽에 모자란 자원이 있을 거라고 생각했다. 그 생각 덕분에 디코딩 문제를 찾았지만, 같은 생각 때문에 거기서 더 찾지 않았다.

## 카메라 사진 한 장에 48.8MB

세 번째 가설은 어떤 사진이 깨지는지 살펴보다가 나왔다. 작은 이미지는 괜찮았지만 카메라로 찍은 사진은 문제였다. 썸네일 로더가 원본 파일에 `UIImage(data:)`를 호출했기 때문에 1200만 화소 사진은 그대로 4032 × 3024 비트맵이 됐다.

| 디코딩 | 화소 | 4바이트/화소 기준 크기 |
|---|---|---|
| 원본 4032 × 3024 | 12.2M | 48.8MB |
| 긴 변 1600 (1600 × 1200) | 1.92M | 7.7MB |
| 긴 변 1200 (1200 × 900), 10월 | 1.08M | 4.3MB |

사진 말풍선이 몇 개만 떠 있어도 원본 해상도 텍스처는 수백 MB가 된다. 당시에는 행이 가장자리를 넘어 다시 합성될 때 GPU가 메모리를 확보하려고 텍스처를 내리는데, 이때 한꺼번에 전부 내린다고 설명했다.

그래서 ImageIO로 다운샘플링했다.

```swift
import ImageIO
import UIKit

func thumbnail(from data: Data, maxPixel: CGFloat) -> UIImage? {
    guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,   // 작은 내장 썸네일은 무시
        kCGImageSourceCreateThumbnailWithTransform: true,     // EXIF 방향 반영
        kCGImageSourceShouldCacheImmediately: true,           // 처음 그릴 때가 아니라 지금 디코딩
        kCGImageSourceThumbnailMaxPixelSize: maxPixel,
    ]
    return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
        .map(UIImage.init(cgImage:))
}
```

전체 화면 뷰어에는 원본을 디코딩하는 경로를 따로 남겨서, 사진을 누르면 여전히 원본 화질로 볼 수 있다. gotchas 파일에는 "오진: 컬링·변환, 원인: 디코드 크기"라고 적었다. 두 번째 시도에서 넣은 `.drawingGroup()`은 코드에 그대로 남았다.

## 10월에 다시 나타난 빈 타일

10월에는 끌어내려 닫는 사진 뷰어와 디스크 캐시를 만들고 있었는데, 사진 말풍선이 다시 가장자리에서 사라지기 시작했다. 관련된 두 파일은 7월 이후 색상 개편 말고는 바뀐 것이 없었다. 7월 수정이 처음부터 불완전했거나, 새로 만든 무언가가 큰 이미지를 다시 화면에 올렸거나 둘 중 하나라고 봤다. 확인해 보니 둘 다였다.

새로 생긴 원인은 뷰어였다. 뷰어는 원본을 디코딩해서 썸네일과 같은 메모리 캐시에 같은 URL 키로 넣고 있었다. 그래서 사진을 열었다 닫으면 말풍선 타일이 자기 URL로 캐시를 찾다가 1200만 화소 이미지를 받아 왔다. 7월에 넣은 다운샘플링은 여전히 돌았지만 캐시 미스일 때만 돌았다.

처음부터 있던 원인은 그리드였다. 뒤집힌 Lazy 리스트 안의 `LazyVGrid`는 보이는 영역을 뒤집힌 좌표로 계산하므로, 말풍선이 화면 끝에 닿는 순간 타일이 화면 밖에 있다고 보고 내려 버린다.

## Grid와 캐시 분리

`LazyVGrid`를 걷어내고 캐시를 나눴다.

```swift
// 1. Grid. 타일은 많아야 10개라 매번 만들어도 비용이 작다.
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

세 번째로 썸네일 상한을 1600px에서 1200px로 낮췄다. 1600은 화면 폭을 꽉 채우는 타일에 맞춘 값이었는데, 타일이 하나인 말풍선은 폭이 260pt쯤이고 3배율이면 780px다. 1200이어도 여유가 있고 타일당 크기는 7.7MB에서 4.3MB로 거의 절반이 된다.

## 메인 액터에 묶인 디코더

그 커밋 38분 뒤에는 같은 빌드에서 생긴 다른 문제를 하나 더 고쳤다. 사진 말풍선이 많은 대화에 들어가면 화면이 굳고 터치가 씹히는 문제였다. 로더는 `Task.detached`에서 디코더를 호출했는데, 프로젝트의 기본 액터 격리(default actor isolation)가 `MainActor`라서 내가 어디에도 적지 않았는데도 디코더 타입이 메인 액터에 묶여 있었다. 즉, 다운샘플링할 때마다 메인 쓰레드로 넘어가고 있었다. 디코더에 `nonisolated`를 붙이고 말풍선 썸네일 작업의 우선순위를 `.utility`로 내려서 이제는 스크롤과 탭보다 뒤에 돈다.

## 475줄을 Nuke로 교체

10월 말에는 이미지 코드가 꽤 불어나 있었다. 디스크 캐시, 같은 요청을 합치고 화면을 벗어난 타일의 작업을 취소하는 다운로더, 메모리 캐시 두 개와 ImageIO 디코더가 있었다. 이걸 전부 Nuke 13으로 바꿨다. Nuke 파이프라인은 원본과 축소본을 디스크와 메모리에 캐시하고, 요청 합치기와 취소, ImageIO 다운샘플링까지 맡는다. 가장 많이 바뀐 iOS 미디어 파일 네 개에서 내 코드 약 475줄이 빠지고 181줄짜리 래퍼가 들어갔다. 대신 Nuke 메이저 버전을 따라가야 하고 업데이트 뒤 모든 사진을 한 번 다시 받아야 하는데, 둘 다 감수하기로 했다.

## 7월 노트에 빠진 것

어느 수정보다 손해가 컸던 건 7월에 남긴 노트였다. 진짜 원인 하나를 찾고 그것을 유일한 원인으로 적었기 때문에, 그 뒤로는 그 메모를 믿고 나도 같이 일하는 코딩 에이전트들도 컬링은 의심하지 않았다. 시뮬레이터에서는 애초에 재현되지 않았으니, 시뮬레이터에서 멀쩡했다는 것은 아무 근거가 되지 못했다.

지금은 gotchas 항목을 두 줄로 나눠 쓴다. 무엇이 증상을 고쳤는지, 그리고 다른 원인 후보를 어떤 근거로 배제했는지다. 이번에 얻은 점검 순서도 하나 있다. 작은 이미지는 되는데 큰 이미지만 하드웨어에서 깨지면 레이아웃보다 디코딩 크기와 메모리를 먼저 본다. 크기가 다른 이미지에는 캐시 키도 따로 준다. Nuke는 축소본을 크기별 키로 나누기 때문에 어느 경로가 먼저 캐시를 채웠든 썸네일 조회가 원본을 받아 올 일이 없다.
