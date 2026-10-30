---
title: "iOS 시뮬레이터를 3.25GB에서 0.86GB로 줄여 병렬 AI 에이전트를 한 맥에 들였다"
description: "기본 시뮬레이터 세 대와 Xcode 빌드 두 개에 36GB 맥이 뻗었다. 세션당 비용을 재고 대여·빌드 슬롯·정리 스크립트로 푼 기록."
date: 2026-10-30 16:07:31 +0900
categories: [AI Agents]
tags: [ios-simulator, xcode, android-emulator, git-worktree, macos, bash]
lang: ko-KR
hidden: true
mermaid: false
ref: parallel-agents-one-mac
permalink: /ko/posts/parallel-agents-one-mac/
math: false
---

iOS 26.5 기본 시뮬레이터 한 대는 프로세스 209개를 띄우고 메모리 3.25GB를 쓴다. 이런 시뮬레이터 세 대에 Xcode 빌드 두 개가 겹치자 36GB 맥이 뻗었다. 기록에 남은 장애 중 CPU 때문인 것은 하나도 없었다. 먼저 메모리가 바닥났고 그다음은 디스크였다. 여유 공간이 230MB까지 내려가자 셸 명령까지 실패했다.

## 세션마다 시뮬레이터를 따로 띄웠다

iOS와 Android 개인 앱을 혼자 만들면서 AI 코딩 에이전트 세션을 여러 개 동시에 돌리기 시작했다. 세션마다 git worktree를 하나씩 준다. 세션은 꼼꼼한 개발자가 할 일을 그대로 한다. 자기 브랜치를 빌드하고 시뮬레이터를 띄워 앱을 깐 뒤 스크린샷을 찍어 결과를 본다. 맥은 14코어 M4 Max에 메모리 36GB다. 시뮬레이터는 iOS 26.5 iPhone 17 Pro였고 Android 쪽은 에뮬레이터 37.2.13에 API 36.1 이미지를 썼다.

메모리가 먼저 모자랐다. 세션마다 3.25GB짜리 기본 시뮬레이터를 따로 띄웠고 세 대가 Xcode 빌드 두 개와 겹치면 맥이 버티지 못했다.

디스크도 금방 찼다. worktree 하나마다 DerivedData가 2~5GB씩 새로 생겼다. Xcode 기본 위치에도 쌓였고 `-derivedDataPath`로 넘긴 `/tmp` 경로나 빌드 폴더에도 쌓였다. 세션마다 이름이 다른 시뮬레이터를 하나씩 만들었는데 한 대가 2~8GB였다. worktree를 지워도 이것들은 그대로 남는다. 고친 날 디스크에 남은 공간은 230MB였다.

시뮬레이터를 세션마다 따로 준 것부터가 한 번 고친 결과였다. 그 전에는 한 대를 같이 썼고 세션끼리 서로의 설치와 화면을 덮어썼다.

## 버린 선택지

결정 기록에 버린 선택지를 이유와 함께 한 줄씩 적어 뒀다.

| 선택지 | 버린 이유 |
|---|---|
| 시뮬레이터 대수만 제한 | 기본 시뮬레이터는 두 대만 돼도 6GB가 넘어 빌드와 겹치면 빠듯하고 병렬 세션 수가 줄어든다 |
| 시뮬레이터 한 대 공유 | 세션끼리 설치와 화면을 덮어썼다. 이미 사고가 났다 |
| DerivedData 하나 공유 | 동시 빌드가 같은 빌드 DB를 잠가 한 줄로 서므로 빌드 두 개를 동시에 돌리는 의미가 없어진다 |
| 헤드리스 시뮬레이터 스트리밍 도구 | 화면 스트리밍과 입력을 푸는 도구라 메모리 문제는 그대로다 |

대신 세션과 맥 사이에 얇은 래퍼 층을 뒀다. 시뮬레이터 한 대를 가볍게 만들고, 상한과 메모리 하한 안에서만 빌려 준다. 정리할 때는 다시 만들 수 있는 것만 지운다. Xcode 동시 빌드 수는 직접 잰 값으로 묶었다.

```
  세션 A ─┐                    ┌─ 시뮬레이터 대여 (부팅 상한 4, 메모리 여유 20%)
  세션 B ─┼─ 래퍼 스크립트 ────┼─ 빌드 슬롯 (xcodebuild 동시 2개)
  세션 C ─┘                    ├─ 에뮬레이터 대여 (상한 3, 읽기 전용 공유 AVD)
                               └─ gc (다시 만들 수 있는 것만, 디스크 30GB 미만일 때)
```

## simslim으로 시뮬레이터 서비스 끄기

시뮬레이터 메모리는 대부분 백그라운드 서비스가 쓴다. Siri·Spotlight·iCloud 같은 서비스가 180개쯤 뜨는데 테스트 중인 앱은 거의 쓰지 않는다. 그래서 simslim을 썼다. 시뮬레이터 안의 launchd 비활성 목록을 고치는 MIT 라이선스 오픈소스 도구다. 호스트와 공유 런타임은 건드리지 않고 `simslim off`나 초기화로 되돌린다. 기본 프로파일은 사진 선택기만 남기고 나머지 범주를 모두 끈다.

| 시뮬레이터 (iPhone 17 Pro, iOS 26.5) | 프로세스 | 메모리 |
|---|---|---|
| 기본 | 209 | 3.25GB |
| simslim dev 프로파일 | 75 | 0.86GB |

이 설정은 `simctl boot`로 다시 띄워도 남아 있고 `simslim verify`로 적용 여부를 본다. 처음 slim을 적용할 때는 58초가 걸린다. 그 뒤로 같은 시뮬레이터를 띄우는 데는 2~13초면 된다. 대가는 원격 푸시·StoreKit·유니버설 링크·iCloud가 꺼진다는 점이다. 이게 필요한 세션을 위해 래퍼에 `--full` 옵션을 뒀다.

## 상한을 둔 시뮬레이터 대여

세션은 래퍼를 거쳐야만 시뮬레이터를 받는다. 래퍼는 시뮬레이터마다 대여 파일을 하나씩 둔다. 상한에 닿으면 45분 넘게 갱신되지 않은 대여부터 회수하고 그래도 자리가 없으면 부팅을 거절한다. 여유 메모리가 20% 밑일 때도 거절한다. macOS에서는 `kern.memorystatus_level`이 그 비율을 바로 알려 준다.

```bash
#!/usr/bin/env bash
set -uo pipefail
udid=${1:?usage: sim-up <udid>}
max_booted=${SIM_MAX_BOOTED:-4}; min_mem=${SIM_MIN_MEM_PCT:-20}
leases="$HOME/Library/Caches/my-sim-leases"; mkdir -p "$leases"

booted_count() { xcrun simctl list devices | grep -c "(Booted)"; }

if [ "$(booted_count)" -ge "$max_booted" ]; then
  for f in "$leases"/*.lease; do                  # 오래된 대여부터 회수
    [ -e "$f" ] || continue
    if [ -n "$(find "$f" -mmin +45)" ]; then
      xcrun simctl shutdown "$(basename "$f" .lease)" 2>/dev/null; rm -f "$f"
    fi
  done
  [ "$(booted_count)" -ge "$max_booted" ] && { echo "sim cap reached" >&2; exit 75; }
fi
mem=$(sysctl -n kern.memorystatus_level)
[ "$mem" -lt "$min_mem" ] && { echo "free memory ${mem}% < ${min_mem}%" >&2; exit 75; }

xcrun simctl boot "$udid" 2>/dev/null; touch "$leases/$udid.lease"
```

눈여겨볼 곳은 종료 코드다. 75는 `EX_TEMPFAIL`이다. 이 코드를 받은 에이전트는 루프를 돌며 다시 시도하지 않고 기다리거나 SwiftUI 프리뷰 렌더로 대신한다.

## info.plist로 주인 없는 DerivedData 찾기

정리 스크립트에는 규칙을 하나만 줬다. 다시 만들 수 없는 것과 쓰는 중인 것은 지우지 않는다. 지우는 대상은 원래 워크스페이스가 사라진 DerivedData, 6시간 넘게 손대지 않은 `/tmp` 빌드 디렉터리, worktree가 없어진 빌드 산출물이다. 12시간 넘게 꺼져 있던 이 프로젝트의 시뮬레이터와 main에 이미 반영됐고 추적 중인 변경이 없는 에이전트 worktree도 지운다. 실행 중인 프로세스의 명령줄에 보이는 경로나 30분 안에 쓰인 경로는 건너뛴다.

DerivedData의 주인은 Xcode가 이미 적어 둔 파일로 찾는다. `~/Library/Developer/Xcode/DerivedData` 아래 폴더마다 `info.plist`가 있고 그 폴더를 만든 워크스페이스 경로가 들어 있다.

```bash
dd="$HOME/Library/Developer/Xcode/DerivedData"
for d in "$dd"/*/; do
  d=${d%/}
  ws=$(/usr/libexec/PlistBuddy -c "Print :WorkspacePath" "$d/info.plist" 2>/dev/null) || continue
  [ -e "$ws" ] && continue                          # 워크스페이스가 살아 있으면 둔다
  ps -axww -o command= | grep -qF "$d" && continue  # 돌고 있는 빌드가 쓰는 중
  [ -n "$(find "$d" -maxdepth 4 -mmin -30 -print -quit)" ] && continue
  echo "orphan: $(du -sh "$d" | cut -f1) $d"        # 실제 실행에서는 rm -rf "$d"
done
```

처음 돌렸더니 여유 공간이 230MB에서 144GB로 늘었다. 지워진 worktree 30여 개의 DerivedData, 빌드 폴더 19개, 12시간 넘게 꺼져 있던 시뮬레이터 17대, 반영이 끝난 worktree 1개가 빠졌다. 지금은 세션이 시작될 때 훅이 디스크 여유와 메모리 여유, 부팅된 시뮬레이터 수를 한 줄로 찍는다. 디스크 여유가 30GB 밑이면 정리를 뒤에서 돌린다.

## Xcode 빌드 두 개를 동시에 재 보니

동시 빌드 수를 어림으로 정하기 싫었다. 같은 14코어 맥에서 generic 시뮬레이터 대상 클린 빌드 시간을 쟀다.

| 구성 | 걸린 시간 |
|---|---|
| 혼자 빌드 | 103초 |
| 두 개 동시 | 159초 (각각 150초, 158초에 끝남) |
| 두 개를 차례로 (계산값) | 206초 |

206 / 159는 약 1.3이다. 두 개를 동시에 돌리면 차례로 돌릴 때보다 1.3배쯤 더 처리한다. 두 배에는 못 미쳐도 버리기 아까운 차이라 기본 슬롯을 2로 정했다.

슬롯은 저장소의 공유 git 디렉터리 아래에 `mkdir`로 만든 디렉터리다. 어느 worktree에서 봐도 이 경로가 같아서 한 저장소의 세션은 모두 한 줄로 선다. 슬롯마다 pid 파일을 두고 주인 프로세스가 죽은 슬롯은 래퍼가 회수한다.

## Android 에뮬레이터는 게스트 RAM 하한에서 멈췄다

Android에서는 세션마다 AVD를 만들지 않았다. 공유 기본 AVD 두 벌 중 하나를 `-read-only`로 헤드리스 콜드 부팅한다. 끄면 설치한 앱이 사라지지만 렌더 확인에는 지장이 없다. 가벼운 AVD는 720×1600 해상도에 Play 스토어·디지털 웰빙·TTS·메시지를 비롯한 앱 26개를 꺼 뒀다.

| AVD (같은 API 36.1 이미지, 콜드 부팅) | 맥 쪽 footprint | 부팅 |
|---|---|---|
| Android Studio 기본 | 2.27GB | |
| 공유 full, 1080×2400 | 약 2.9GB | 35초 |
| 공유 lite, 720×1600 | 약 1.9GB | 17~22초 |

iOS만큼은 줄지 않았다. 호스트 메모리의 대부분은 이미지의 게스트 RAM 하한(36.1은 2560MB)이 정한다. 앱을 꺼서 아끼는 몫은 게스트가 실제로 건드린 페이지만큼이다. 다른 길도 셋 가 봤지만 모두 막혔다.

- ATD(Automated Test Device) 이미지는 게스트 프로세스를 263개로 줄였다. 그런데 host·swangle·guest 어느 GPU 모드에서도 스크린샷이 까맣게 나와 렌더 확인에 쓸 수 없었다. API 37 ATD 이미지는 16KB 페이지를 써서 RAM 하한이 4096MB로 오르고 맥에서 2.32GB를 썼다.
- 스냅샷 부팅은 3초 만에 떴다. 하지만 스냅샷을 읽기 전용으로 열자 게스트 RAM을 통째로 복사했고 footprint가 3.2GB가 됐다.
- `avdmanager`로 만든 AVD는 이 맥에서 `hvf is not enabled`와 `mprotect failed`를 내며 뜨지 않았다. 그래서 래퍼가 Studio 형식의 최소 config를 직접 쓴다. 에이전트 샌드박스 안에서 에뮬레이터를 띄워도 같은 HVF 오류가 난다. 래퍼는 이를 알아채고 샌드박스 밖에서 실행하라고 알려 준다.

## `set -u`에서 죽은 거절 메시지

같은 날 오후 한 세션이 에뮬레이터 부팅 상한에 걸렸다. 스크립트는 거절 메시지를 찍는 대신 죽었고 세션은 상한 환경 변수를 올려서 지나갔다. 시뮬레이터 래퍼와 에뮬레이터 래퍼 모두 거절 메시지에 대수를 `$n대`처럼 한글 단위 바로 앞에 붙여 찍었다. UTF-8 로케일에서 `set -u`가 켜져 있으면 bash는 `$n` 뒤의 바이트까지 변수 이름으로 읽는다.

```
$ LC_ALL=en_US.UTF-8 bash -uc 'n=3; echo "x $n대 y"'
bash: n�: unbound variable
$ LC_ALL=C bash -uc 'n=3; echo "x $n대 y"'
x 3대 y
```

macOS 기본 bash 3.2.57과 Homebrew bash 5.3.9에서 모두 재현했다. `${n}대`로 쓰면 해결된다.

정작 눈에 들어온 건 세션이 한 일이다. 가드가 요란하게 실패하자 에이전트는 이를 장애물로 보고 돌아갔다. 처음 있는 일도 아니었다. 그 전 시험 운행에서는 막힌 워커가 자기 몫이 아닌 경로의 파일을 고쳐서 빠져나갔다.

## 남의 빌드를 깔고 남의 창을 누른 세션

작은 충돌도 두 번 있었다. 스크린샷 스크립트는 원래 "DerivedData에서 가장 최근 `.app`"을 골라 설치했는데 한 번은 그게 다른 worktree의 빌드였다. 지금은 `xcodebuild -showBuildSettings`에서 자기 빌드의 `CODESIGNING_FOLDER_PATH`를 받아 쓴다. 시뮬레이터 창이 겹쳐서 합성 탭이 다른 세션의 창에 들어간 적도 있다. 이제는 창 제목으로 자기 창을 찾고 그 안의 기기 화면을 기준으로 탭 좌표를 잡는다.

## 바꾸기 전과 후

시뮬레이터 메모리는 `simslim measure`로, 에뮬레이터는 맥 쪽 `footprint`로 쟀다.

| 자원 | 전 | 후 |
|---|---|---|
| iOS 시뮬레이터, 세션당 | 3.25GB, 프로세스 209 | 0.86GB, 프로세스 75 |
| Android 에뮬레이터, 세션당 | 2.27GB (Studio 기본) | 약 1.9GB (읽기 전용 공유 lite AVD) |
| 디스크 여유 | 230MB | 첫 정리 뒤 144GB |
| Xcode 동시 빌드 | 제한 없음 | 슬롯 2, 차례로 빌드할 때의 1.3배 처리량 |

이 대당 수치로 셈하면 slim 시뮬레이터 네 대가 약 3.4GB다. 기본 시뮬레이터 세 대는 약 9.75GB였다.

## 거절 경로부터 시험한다

세션 하나의 비용을 알고 나니 해법은 평범한 운영체제 발상이었다. 만료되는 대여, 거절 코드가 있는 할당량, 잰 값으로 크기를 정한 세마포어, 다시 만들 수 있는 것만 지우는 가비지 컬렉션이다. 세션을 늘리기 전에는 세션 하나가 무엇을 얼마나 쓰는지부터 센다.

에이전트에게는 하나가 더 필요하다. 내 기록에서 에이전트는 실패를 만날 때마다 가장 짧은 길로 돌아갔고 가드도 예외가 아니었다. 그래서 가드는 거절 이유를 분명히 찍고 "기다려라"를 뜻하는 종료 코드로 끝나야 한다. 거절 경로는 에이전트보다 먼저 직접 밟아 본다. 변수 바로 뒤에 한글 같은 비ASCII 문자를 붙인 메시지라면 위의 `LC_ALL=en_US.UTF-8 bash -uc` 한 줄로 시험해 보길 권한다.
