---
title: "폴드7 오른쪽 끝의 빛줄기는 16의 배수가 아닌 버퍼 폭에서 나왔다"
description: "릴리스 빌드에서 효과를 하나씩 끄는 스위치로 Android에서만 보인 bloom 빛줄기를 버퍼 폭 정렬 문제로 좁히고, 80fps인데 버벅이던 끌기를 60Hz 페이싱으로 고쳤다."
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

갤럭시 Z 폴드7 겉화면에서 내 앱의 3D 방을 띄우면 오른쪽 가장자리를 따라 흰색·초록색·보라색 빛이 번졌다. bloom을 끄자 사라졌다. 렌더 버퍼 폭을 1080에서 832픽셀로 바꿔도 사라졌는데 824에서는 그대로 남았다. 멀쩡한 폭은 16의 배수였다.

같은 날 밤 같은 화면의 버벅임도 고쳤다. 프레임 수는 약 80fps로 나오는데 끌어서 둘러볼 때 덜컥거렸다. 두 수정 모두 그날 밤 넣은 스위치에서 나왔다. 다시 빌드하지 않고 릴리스 빌드에서 렌더링 기능을 끄는 스위치다.

## SurfaceView 안의 Filament 방

앱 홈 화면은 작은 3D 방이다. Filament 1.79를 직접 만든 C++ 브리지로 그린다. Android에서는 OpenGL ES 백엔드를 쓰고 이 기기의 GPU는 Adreno다. 화면은 Compose `AndroidView` 안의 `SurfaceView`이고 `Choreographer` 콜백이 프레임을 돌린다. 같은 장면과 같은 GLB 파일이 iOS에서는 Metal로 돈다.

두 문제 모두 기기에 깐 릴리스 빌드에서 봤다. 오른쪽 가장자리의 빛과 고르지 않은 끌기다. 그전 확인에서는 둘 다 안 보였는데 첫 번째는 이유가 단순하다. Android 렌더 확인을 에뮬레이터에서 후처리를 끈 "plain" 모드로 했고 bloom은 후처리다. 문제를 만든 효과가 내가 보던 설정에서는 한 번도 켜진 적이 없었다. Mac에서 Metal로 그린 804폭 화면도 16의 배수가 아니었지만 깨끗했다.

## adb로 켜고 끄는 스위치

렌더링 결함을 다시 빌드해 가며 짐작하면 느리다. 문제가 보인 그 빌드를 그대로 보고 싶기도 했다. 그래서 3D 화면을 만들 때 네이티브 코드가 읽는 시스템 속성을 몇 개 넣었다. `debug.`로 시작하는 속성은 일반 기기에서도 `adb shell`로 바꿀 수 있으니 릴리스 APK에 그대로 쓸 수 있다.

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

속성은 두 개가 더 있다. 하나는 버퍼 밀도 상한이고 다른 하나는 N장마다 GPU 시간 p50·p95를 로그로 남긴다. 속성을 바꾸고 화면을 다시 연 다음 같은 자리를 본다.

```bash
adb shell setprop debug.myapp.render.off bloom
adb shell setprop debug.myapp.render.log 300   # 300장마다 GPU p50/p95
```

## 버퍼 폭 다섯 가지

효과를 하나씩 꺼 봤다. 빛줄기는 bloom을 끌 때만 사라졌다. bloom이 문제를 퍼뜨리는 건 분명했다. 하지만 Metal 렌더와 다른 폭에서는 가장자리가 깨끗했으니 bloom이 문제를 만든다고 보기는 어려웠다. bloom은 밝은 픽셀을 넓게 흐린다. 가장자리의 잘못된 열 하나도 눈에 띄는 얼룩이 된다.

다음으로 버퍼 폭을 바꿔 봤다.

| 버퍼 폭 | 16의 배수 | 오른쪽 빛줄기 |
|---|---|---|
| 1080 | 아님 (67.5 × 16) | 있음 |
| 824 | 아님 (51.5 × 16) | 있음 |
| 784 | 맞음 | 없음 |
| 800 | 맞음 | 없음 |
| 832 | 맞음 | 없음 |

내 해석은 이렇다. 폭이 16으로 정렬되지 않으면 이 GPU와 드라이버에서는 후처리 버퍼의 마지막 열에 쓰레기 값이 남고 bloom이 그 값을 번지게 한다.

## 16에 맞춘 고정 버퍼

`SurfaceView`에 늘 16의 배수인 고정 버퍼 크기를 줬다. 손댄 김에 렌더 밀도도 2로 묶었다. iOS 호스트가 쓰는 상한과 같다. 버퍼를 뷰 크기로 늘리는 일은 화면 합성기가 맡는다.

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

가로세로를 따로 반올림하니 비율이 조금 바뀐다. 이 크기들에서는 왜곡이 0.5% 안이었다.

손이 간 곳이 두 군데 있었다. 버퍼가 뷰보다 작아지면 걷기나 물건 누르기 같은 터치 판정은 뷰 크기로 해야 한다. 그래서 호스트에 두 크기를 모두 넘긴다. 또 폰을 접거나 펴면 뷰 크기만 바뀌고 고정 버퍼 크기는 그대로라서 `surfaceChanged`가 오지 않는다. 이때는 `SurfaceView`의 레이아웃 변경 리스너가 크기를 다시 계산한다.

맨 오른쪽 열의 거칠기 점수는 바꾸기 전 24.4에서 바꾼 뒤 5.3이 됐다. 안쪽 열의 4~6 범위 안이다.

## 120Hz 화면에 13~20ms짜리 프레임

겉화면은 120Hz로 돌고 `Choreographer`는 vsync마다, 즉 8.3ms마다 프레임 콜백을 불렀다. 끄는 동안 GPU는 한 장에 13~20ms가 걸렸다. 그 사이 GPU 클럭은 최대 1,200MHz 중 222~443MHz에 머물러서 제 속도로 돌지도 않았다. vsync 한 칸보다 오래 걸린 프레임은 다음 빈칸에 나가니 프레임 간격이 8·16·24ms로 섞였다. 약 80fps는 숫자로는 60보다 좋았다. 손에는 더 나빴다.

아무것도 움직이지 않을 때도 방은 계속 그려졌다. 정지 상태에서 69fps였다.

표시 간격은 SurfaceFlinger timestats로 끌기 세 번을 고치기 전후로 쟀다.

| 지표 (끌기 3회, SurfaceFlinger timestats) | 이전 | 이후 |
|---|---|---|
| 끄는 동안 프레임 수 | 약 80fps | 59~60fps |
| 16ms 간격 비율 | 45% | 70~77% |
| 8ms 간격 비율 | 51% | 해당 없음 |
| 8ms + 24ms 쌍 | 해당 없음 | 11~15% |
| 25ms 넘는 간격 | 해당 없음 | 0.2~1.2% |
| 정지 중 그린 프레임 | 69fps | 0 |

세 가지를 바꿨다.

- 프레임 콜백은 약 16.7ms가 지날 때까지 vsync를 건너뛴다. 흔들림 때문에 프레임을 놓치지 않게 vsync 반 칸만큼 여유를 둔다.
- 서피스가 자신을 60fps 원본이라고 알린다. 다른 요소가 120을 원하지 않으면 화면이 60Hz로 내려갈 수 있다.
- 네이티브 쪽은 바뀐 것이 있을 때만 그리고 그 뒤 8장을 더 그려 시간 축 안티앨리어싱이 자리 잡게 한다. iOS 호스트는 이미 이렇게 돌고 있었다.

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

시도했다가 뺀 것도 셋 있다. `setPresentationTime`과 ADPF 성능 힌트는 둘 다 반복 측정 사이의 차이보다 작게 움직였다. 해상도를 1.5배 낮춰도 GPU 시간은 그대로였으니 이 기기에서 이 장면의 병목은 픽셀 수가 아니다. iOS에서 동적 해상도가 이 장면에 거의 도움이 안 됐던 것과도 맞는다.

## GPU 시간은 아직 예산을 넘는다

페이싱 수정은 프레임을 고르게 했을 뿐 싸게 만들지는 못했다. 조작 중 GPU 시간은 여전히 p50 15~16ms, p95 19~21ms다. 이 장면에 정해 둔 예산 12ms를 넘는다.

## 출시 빌드에서 효과 끄기

이날 만든 것 중 가장 싼 게 속성 스위치였다. 다음에는 첫 불만이 나오기 전에 넣어 둘 생각이다. 출시 빌드에서 효과를 하나씩 끄니 "오른쪽에 이상한 빛이 있다"가 "bloom, 그리고 16의 배수가 아닌 폭"으로 몇 번 만에 좁혀졌다.

에뮬레이터 렌더도 진짜 렌더였지만 후처리가 없는 설정이었고 결함은 전부 후처리 안에 있었다. 스크린샷 비교는 찍을 때 켜져 있던 기능만 확인한다.
