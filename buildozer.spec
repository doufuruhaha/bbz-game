[app]
title = 八宝粥行动
package.name = bbzgame
package.domain = org.bbz

source.dir =tu.ico
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,json

version = 0.1

requirements = python3==3.10.12,kivy==2.3.0,hostpython3==3.10.12,pyjnius==1.5.0,pygame,requests,websocket-client

orientation = landscape
fullscreen = 1

android.permissions = INTERNET
android.allow_backup = True

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

android.archs = arm64-v8a, armeabi-v7a

p4a.branch = master
p4a.bootstrap = sdl2
