---
title: "[Django] Pycharm에서 Django 프로젝트 생성하기"
excerpt: "Pycharm Community Edition으로 Django 프레임워크 프로젝트 생성"
toc: true
toc_sticky: true
categories: [Web]
tags: [Web, Django, Python, Pycharm, Pycharm Community Edition]
---

## Pycharm에서 새 프로젝트를 생성
Pycharm Community Edition으로 Django 프로젝트를 시작해 보자.<br>
우선 Pycharm에서 새 프로젝트를 만든다.

![]({{ site.url }}/assets/images/[Django]1-1.png ){: .align-center}

## 인터프리터 등록
새 프로젝트의 인터프리터를 등록해야 한다. <br>
인터프리터를 등록하는 방법은 2가지가 있다. <br>
1. 새 프로젝트에서 가상환경을 만든 후 Django를 pip으로 설치
2. 미리 가상환경을 만들고 Django를 설치한 후 프로젝트에서 해당 가상환경을 등록

1번 방법으로 새 프로젝트를 인터프리터를 설정하자.

![]({{ site.url }}/assets/images/[Django]1-2.png ){: .align-center}

## Django 설치
새 프로젝트에 Django를 설치해 보자. <br>
File에 Settings(Ctrl + Alt + S)를 누른다. <br>

![]({{ site.url }}/assets/images/[Django]1-3.png ){: .align-center}

Install(Alt + Insert)를 눌러 Django 패키지를 설치한다. <br>

![]({{ site.url }}/assets/images/[Django]1-4.png ){: .align-center}

![]({{ site.url }}/assets/images/[Django]1-5.png ){: .align-center}

## Django 프로젝트 생성
Alt + F12를 눌러 터미널을 킨 후 Django 프로젝트를 생성한다. <br>

`django-admin startproject temp`
> `temp` 프로젝트 생성함

![]({{ site.url }}/assets/images/[Django]1-6.png ){: .align-center}

위 사진처럼 temp 폴더가 생성된다. temp 폴더 안에 들어가 보면 temp 라는 기본 앱과 manage.py가 있다. <br>
manage.py는 Django 프로젝트에서 사용할 명령어들을 위한 파일이라고 생각하면 된다. <br>

![]({{ site.url }}/assets/images/[Django]1-7.png ){: .align-center}

## Django Application 생성
temp 폴더로 이동한 후 터미널에 다음과 같이 입력한다. <br>

`python manage.py startapp tempApp`
> `tempApp` Application 생성함

![]({{ site.url }}/assets/images/[Django]1-8.png ){: .align-center}

## 서버실행
터미널에서 서버를 실행해 보자. <br>

`python manage.py runserver`
> 기본 8000 포트로 서버가 실행된다. 사용자 지정 포트를 열 수도 있다.

![]({{ site.url }}/assets/images/[Django]1-9.png ){: .align-center}

localhost:8000에 접속하여 다음과 같은 화면이 뜨면 성공적으로 서버가 실행된 것이다.

![]({{ site.url }}{/assets/images/[Django]1-10.png ){: .align-center}

서버는 Ctrl + C로 끌 수 있다. /