[app]
title = 八宝粥行动
package.name = bbzgame
package.domain = org.bbz

source.dir =to.ico
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,json
source.exclude_dirs = tests, bin, .github, data

version = 0.1

# Python 3.10 + Kivy + Pygame + 网络请求
requirements = python3==3.10.12,kivy==2.3.0,hostpython3==3.10.12,pyjnius==1.5.0,pygame,requests,websocket-client

orientation = landscape
fullscreen = 1

android.permissions = INTERNET
android.allow_backup = True
android.accept_sdk_license = True

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

android.archs = arm64-v8a, armeabi-v7a

# 禁用 Kivy 启动画面（Pygame 项目不需要）
presplash.filename = 

# Pygame 相关
p4a.branch = master
p4a.bootstrap = sdl2
