[app]
title = Gabaritus
package.name = gabaritusapp
package.domain = com.jocelio.gabaritus
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,json,xlsx,csv,zip,db
requirements = hostpython3==3.11.11, python3==3.11.11, kivy==2.3.0, kivymd==2.0.1dev0, fpdf, pillow, android
orientation = portrait
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, CAMERA
android.api = 33
android.minapi = 21
android.ndk = 25b
strip = True
compression = True
android.archs = arm64-v8a
version = 1.0.0
version.release = 1
log_level = 2
android.accept_sdk_license = True

[buildozer]
log_dir = ./.buildozer/logs
build_dir = ./.buildozer
