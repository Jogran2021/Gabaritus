[app]
title = Gabaritus
package.name = gabaritusapp
package.domain = com.gabaritus
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt,md,json
version = 0.1
requirements = hostpython3==3.11.11,python3==3.11.11,kivy==2.3.0,kivymd==2.1.0,Pillow,pyjnius,fpdf2
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 1
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.arch = arm64-v8a
android.allow_backup = True
android.undeprecated_sdk = True
