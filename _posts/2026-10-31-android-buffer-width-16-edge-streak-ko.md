---
title: "안드로이드 Filament 버퍼 폭 정렬과 가장자리 줄무늬"
description: "갤럭시 Z 폴드7에서 3D 방 오른쪽 가장자리에 블룸 줄무늬가 생겼고, 드래그는 약 80fps인데도 버벅였다. 원인은 16의 배수가 아닌 버퍼 폭과 120Hz에서 고르지 않은 프레임 간격이었다."
date: 2026-10-31 01:28:50 +0900
categories: [Graphics]
tags: [android, filament, opengl-es, frame-pacing, surfaceview]
lang: ko-KR
hidden: true
mermaid: false
ref: android-buffer-width-16-edge-streak
permalink: /ko/posts/android-buffer-width-16-edge-streak/
math: false
---

갤럭시 Z 폴드7 커버 화면에서 내 앱의 3D 방을 띄우면 오른쪽 가장자리를 따라 흰색·초록색·보라색 빛이 번졌다. 블룸을 끄면 사라졌고, 렌더 버퍼 폭을 1080에서 832픽셀로 바꿔도 사라졌는데 824에서는 그대로 남았다. 멀쩡했던 폭은 모두 16의 배수였다.

같은 날 밤에는 같은 화면의 버벅임도 고쳤다. 프레임 레이트는 약 80fps로 나오는데 드래그해서 둘러볼 때 덜컥거리는 문제였다. 두 문제 모두 그날 밤 넣은 스위치 덕분에 풀었다. 다시 빌드하지 않고도 릴리즈 빌드에서 렌더링 기능을 끌 수 있는 스위치다.

## SurfaceView 안의 Filament 방

앱 홈 화면은 작은 3D 방이고, Filament 1.79를 직접 만든 C++ 브리지로 그린다. 안드로이드에서는 OpenGL ES 백엔드를 쓰며 이 기기의 GPU는 Adreno다. 화면은 Compose `AndroidView` 안의 `SurfaceView`이고 `Choreographer` 콜백이 프레임마다 그리기를 호출한다. 같은 장면과 같은 GLB 파일이 iOS에서는 Metal로 돈다.

오른쪽 가장자리의 빛과 고르지 않은 드래그, 두 문제 모두 기기에 설치한 릴리즈 빌드에서 봤다. 그전 확인에서는 둘 다 보이지 않았는데, 첫 번째 문제는 이유가 단순하다. 안드로이드 렌더링 확인을 에뮬레이터에서 후처리를 끈 "plain" 모드로 했는데 블룸은 후처리이므로, 문제를 만든 효과가 내가 보던 설정에서는 한 번도 켜진 적이 없었다. Mac에서 Metal로 그린 폭 804픽셀 화면도 16의 배수가 아니었지만 깨끗했다.

## adb로 켜고 끄는 스위치

렌더링 아티팩트를 짐작으로 고쳐 가며 매번 다시 빌드하면 느리고, 무엇보다 문제가 보인 바로 그 빌드에서 확인하고 싶었다. 그래서 3D 화면을 만들 때 네이티브 코드가 읽는 시스템 속성을 몇 개 넣었다. `debug.`로 시작하는 속성은 일반 기기에서도 `adb shell`로 바꿀 수 있으므로 릴리즈 APK에 그대로 쓸 수 있다. 코드는 다음과 같다.

```cpp
#include <sys/system_properties.h>
#include <string>

// "debug.myapp.render.off"에 쉼표 목록을 넣는다. 예: "bloom,taa"
bool featureOff(const char* name) {
    char value[PROP_VALUE_MAX] = {0};
    if (__system_property_get("debug.myapp.render.off", value) <= 0) return false;
    const std::string list = "," + std::string(value) + ",";
    return list.find("," + std::string(name) + ",") != std::string::npos;
}

void applySwitches(filament::View* view) {
    if (featureOff("bloom")) {
        auto bloom = view->getBloomOptions();
        bloom.enabled = false;
        view->setBloomOptions(bloom);
    }
    if (featureOff("post")) view->setPostProcessingEnabled(false);
    // taa, ao, 그림자, 정지 시 건너뛰기도 같은 모양
}
```

속성은 두 개가 더 있는데, 하나는 버퍼 density 상한을 정하고, 다른 하나는 N장마다 GPU 시간 p50·p95를 로그로 남긴다. 속성을 바꾸고 화면을 다시 연 다음 같은 자리를 보면 된다.

```bash
adb shell setprop debug.myapp.render.off bloom
adb shell setprop debug.myapp.render.log 300   # 300장마다 GPU p50/p95
```

## 버퍼 폭 다섯 가지 비교

효과를 하나씩 꺼 보니 줄무늬는 블룸을 끌 때만 사라졌다. 블룸이 문제를 퍼뜨리는 것은 분명했지만, Metal 렌더와 다른 폭에서는 가장자리가 깨끗했으므로 블룸이 문제를 만든다고 보기는 어려웠다. 블룸은 밝은 픽셀을 넓게 흐리기 때문에, 가장자리의 잘못된 열 하나도 눈에 띄는 얼룩이 된다.

다음으로 버퍼 폭을 바꿔 봤다. 결과는 다음과 같다.

| 버퍼 폭 | 16의 배수 | 오른쪽 줄무늬 |
|---|---|---|
| 1080 | 아님 (67.5 × 16) | 있음 |
| 824 | 아님 (51.5 × 16) | 있음 |
| 784 | 맞음 | 없음 |
| 800 | 맞음 | 없음 |
| 832 | 맞음 | 없음 |

내 해석은 이렇다. 폭이 16으로 정렬되지 않으면 이 GPU와 드라이버에서는 후처리 버퍼의 마지막 열에 쓰레기 값이 남고, 블룸이 그 값을 번지게 한다.

## 16의 배수로 맞춘 고정 버퍼

`SurfaceView`에 항상 16의 배수인 고정 버퍼 크기를 지정했다. 손댄 김에 렌더 density도 iOS 호스트와 같은 상한인 2로 묶었다. 버퍼를 뷰 크기로 늘리는 일은 SurfaceFlinger(컴포지터)가 한다.

```kotlin
private const val MAX_DENSITY = 2f
private const val ALIGN = 16

fun bufferSize(view: View): Pair<Int, Int> {
    val density = view.resources.displayMetrics.density
    val scale = if (density <= MAX_DENSITY) 1f else MAX_DENSITY / density
    fun align(v: Float) = maxOf(ALIGN, (v / ALIGN).roundToInt() * ALIGN)
    val width = align(view.width * scale)
    val height = align(width * view.height.toFloat() / view.width)
    return width to height
}

// surfaceChanged와 레이아웃 변경 때
val (w, h) = bufferSize(surfaceView)
surfaceView.holder.setFixedSize(w, h)
```

가로세로를 따로 반올림하므로 비율이 조금 바뀌는데, 이 크기들에서는 왜곡이 0.5% 이내였다.

신경 쓸 곳이 두 군데 더 있었다. 버퍼가 뷰보다 작아지면 걷기나 물건 누르기 같은 터치 판정은 뷰 크기로 해야 하므로, 호스트에 두 크기를 모두 넘기도록 했다. 또 폰을 접거나 펴면 뷰 크기만 바뀌고 고정 버퍼 크기는 그대로라서 `surfaceChanged`가 호출되지 않는다. 이때는 `SurfaceView`의 레이아웃 변경 리스너에서 크기를 다시 계산한다.

맨 오른쪽 열의 거칠기 값은 바꾸기 전 24.4에서 바꾼 뒤 5.3으로 내려와, 안쪽 열들의 범위(4~6) 안에 들어왔다.

## 120Hz 화면에 13~20ms짜리 프레임

커버 화면은 120Hz로 돌고, `Choreographer`는 vsync(화면 갱신 신호)마다, 즉 8.3ms마다 프레임 콜백을 불렀다. 그런데 드래그하는 동안 GPU는 한 장에 13~20ms가 걸렸고, 그 사이 GPU 클럭은 최대 1,200MHz 중 222~443MHz에 머물러 제 속도로 돌지도 않았다. vsync 한 칸보다 오래 걸린 프레임은 그다음 vsync에 화면에 나가므로 프레임 간격이 8·16·24ms로 섞였다. 약 80fps는 숫자로는 60fps보다 좋았지만 직접 만져 보면 더 나빴다.

게다가 아무것도 움직이지 않을 때도 방은 계속 그려지고 있었다. 정지 상태에서 69fps였다.

프레임 간격은 고치기 전과 후에 각각 드래그를 세 번 하며 SurfaceFlinger timestats로 측정했다.

| 지표 (드래그 3번, SurfaceFlinger timestats) | 이전 | 이후 |
|---|---|---|
| 드래그 중 프레임 수 | 약 80fps | 59~60fps |
| 16ms 간격 비율 | 45% | 70~77% |
| 8ms 간격 비율 | 51% | 해당 없음 |
| 8ms + 24ms 쌍 | 해당 없음 | 11~15% |
| 25ms 넘는 간격 | 해당 없음 | 0.2~1.2% |
| 정지 중 그린 프레임 | 69fps | 0 |

바꾼 것은 세 가지다.

- 프레임 콜백은 약 16.7ms가 지날 때까지 vsync를 건너뛴다. 지터 때문에 프레임을 놓치지 않도록 vsync 반 칸만큼 여유를 둔다.
- 서피스를 60fps 소스로 지정한다. 다른 요소가 120을 원하지 않으면 화면이 60Hz로 내려갈 수 있다.
- 네이티브 쪽은 바뀐 것이 있을 때만 그리고, 그 뒤 8장을 더 그려 TAA가 안정되게 한다. iOS 호스트는 이미 이렇게 돌고 있었다.

```kotlin
private const val FRAME_NS = 16_666_667L
private const val HALF_VSYNC_NS = 4_166_667L   // 120Hz 한 칸의 절반

override fun doFrame(vsyncNanos: Long) {
    if (last != 0L && vsyncNanos - last < FRAME_NS - HALF_VSYNC_NS) {
        choreographer.postFrameCallback(this)  // 이르다. 다음 vsync를 기다린다
        return
    }
    last = vsyncNanos
    renderer.renderIfDirty(vsyncNanos)          // 바뀐 게 없으면 네이티브가 건너뛴다
    choreographer.postFrameCallback(this)
}

// 서피스를 만들 때 한 번 (API 30 이상)
surface.setFrameRate(60f, Surface.FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)
```

시도했다가 뺀 것도 세 가지 있다. `setPresentationTime`과 ADPF 성능 힌트는 둘 다 효과가 반복 측정 사이의 편차보다 작았다. 해상도를 1.5배 낮춰도 GPU 시간은 그대로였으므로, 이 기기에서 이 장면의 병목은 픽셀 수가 아니다. iOS에서 동적 해상도가 이 장면에 거의 도움이 되지 않았던 것과도 맞는다.

## 아직 예산을 넘는 GPU 시간

프레임 페이싱을 고쳐서 프레임 간격은 고르게 만들었지만 프레임 비용을 줄이지는 못했다. 조작 중 GPU 시간은 여전히 p50 15~16ms, p95 19~21ms로, 이 장면에 정해 둔 예산 12ms를 넘는다.

## 정리

이날 만든 것 중 가장 손이 덜 간 것이 속성 스위치였으므로, 다음에는 문제가 보이기 전에 미리 넣어 둘 생각이다. 릴리즈 빌드에서 효과를 하나씩 끄니 "오른쪽에 이상한 빛이 있다"던 증상이 몇 번 만에 "블룸, 그리고 16의 배수가 아닌 폭"으로 좁혀졌다.

에뮬레이터 화면도 실제 렌더링이었지만 후처리가 없는 설정이었고, 아티팩트는 전부 후처리 안에서 생겼다. 스크린샷 비교는 찍을 때 켜져 있던 기능만 확인해 준다.
