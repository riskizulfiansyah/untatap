#!/usr/bin/env python3
"""
Builder untuk macOS .app bundle (arm64 Apple Silicon only) Tatap.
Mendownload Python 3.11 standalone, memasang dependensi pip,
menyalin backend & frontend, menyalin template Info.plist,
mengompilasi launcher Go dengan webview_go, dan melakukan ad-hoc code sign.
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import tarfile
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(ROOT_DIR, "dist")
CACHE_DIR = os.path.join(ROOT_DIR, ".build_cache")

PYTHON_TAR_URL = "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.11.9+20240415-aarch64-apple-darwin-install_only.tar.gz"
PYTHON_TAR_NAME = "cpython-3.11.9-aarch64-apple-darwin.tar.gz"

APP_DIR = os.path.join(DIST_DIR, "Tatap.app")
CONTENTS_DIR = os.path.join(APP_DIR, "Contents")
MACOS_DIR = os.path.join(CONTENTS_DIR, "MacOS")
RESOURCES_DIR = os.path.join(CONTENTS_DIR, "Resources")
RUNTIME_DIR = os.path.join(RESOURCES_DIR, "runtime")


def log(msg):
    print(f"\n[BUILD-MACOS] {msg}")


def download_file(url, target_path, retries=3):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        log(f"Menggunakan file cache: {os.path.basename(target_path)}")
        return
    log(f"Mengunduh {url} ...")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as f:
                shutil.copyfileobj(resp, f)
            log(f"Selesai mengunduh {os.path.basename(target_path)}")
            return
        except Exception as e:
            if attempt == retries:
                raise e
            time.sleep(2)


def setup_standalone_python():
    tar_path = os.path.join(CACHE_DIR, PYTHON_TAR_NAME)
    download_file(PYTHON_TAR_URL, tar_path)

    log(f"Mengekstrak Python standalone ke {RUNTIME_DIR} ...")
    if os.path.exists(RUNTIME_DIR):
        shutil.rmtree(RUNTIME_DIR)
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    temp_extract = os.path.join(CACHE_DIR, "py_temp_mac")
    if os.path.exists(temp_extract):
        shutil.rmtree(temp_extract)
    os.makedirs(temp_extract, exist_ok=True)

    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(path=temp_extract)

    extracted_python = os.path.join(temp_extract, "python")
    if os.path.exists(extracted_python):
        for item in os.listdir(extracted_python):
            src_item = os.path.join(extracted_python, item)
            dst_item = os.path.join(RUNTIME_DIR, item)
            if os.path.exists(dst_item):
                if os.path.isdir(dst_item):
                    shutil.rmtree(dst_item)
                else:
                    os.remove(dst_item)
            shutil.move(src_item, dst_item)
    shutil.rmtree(temp_extract, ignore_errors=True)

    py_bin = os.path.join(RUNTIME_DIR, "bin", "python3")
    if not os.path.exists(py_bin):
        raise RuntimeError(f"Python binary tidak ditemukan di {py_bin}")
    os.chmod(py_bin, 0o755)
    log(f"Python standalone siap di {py_bin}")


def install_dependencies():
    py_bin = os.path.join(RUNTIME_DIR, "bin", "python3")
    req_file = os.path.join(ROOT_DIR, "requirements.txt")

    log("Memasang dependensi Python macOS via pip...")
    subprocess.run([py_bin, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"], check=True)
    subprocess.run([py_bin, "-m", "pip", "install", "-r", req_file], check=True)
    log("Dependensi Python berhasil dipasang.")


def copy_project_files():
    log("Menyalin kode backend, frontend, dan versi...")
    backend_dst = os.path.join(RESOURCES_DIR, "backend")
    if os.path.exists(backend_dst):
        shutil.rmtree(backend_dst)
    shutil.copytree(
        os.path.join(ROOT_DIR, "backend"),
        backend_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "anime.db*")
    )

    frontend_dst = os.path.join(RESOURCES_DIR, "frontend")
    if os.path.exists(frontend_dst):
        shutil.rmtree(frontend_dst)
    shutil.copytree(os.path.join(ROOT_DIR, "frontend"), frontend_dst)

    version_src = os.path.join(ROOT_DIR, "VERSION")
    if os.path.exists(version_src):
        shutil.copy2(version_src, os.path.join(RESOURCES_DIR, "VERSION"))


def prepare_icon():
    ico_path = os.path.join(ROOT_DIR, "launcher", "icon.ico")
    icns_path = os.path.join(RESOURCES_DIR, "icon.icns")
    if os.path.exists(ico_path):
        log("Mengonversi icon.ico ke icon.icns via sips...")
        iconset_dir = os.path.join(CACHE_DIR, "icon.iconset")
        if os.path.exists(iconset_dir):
            shutil.rmtree(iconset_dir)
        os.makedirs(iconset_dir, exist_ok=True)
        # Ekstrak/konversi sederhana via sips atau copy
        try:
            subprocess.run(["sips", "-s", "format", "icns", ico_path, "--out", icns_path], check=True)
        except Exception:
            # Fallback copy png jika ada
            png_path = os.path.join(ROOT_DIR, "assets", "tatap_icon_512.png")
            if os.path.exists(png_path):
                subprocess.run(["sips", "-s", "format", "icns", png_path, "--out", icns_path], check=True)


def build_launcher():
    log("Mengompilasi launcher Go (Tatap) untuk arm64 macOS...")
    launcher_dir = os.path.join(ROOT_DIR, "launcher")
    target_exe = os.path.join(MACOS_DIR, "Tatap")

    env = os.environ.copy()
    env["GOOS"] = "darwin"
    env["GOARCH"] = "arm64"
    env["CGO_ENABLED"] = "1"

    cmd = [
        "go", "build",
        "-ldflags", "-s -w",
        "-trimpath",
        "-o", target_exe,
        "."
    ]
    subprocess.run(cmd, env=env, check=True, cwd=launcher_dir)
    os.chmod(target_exe, 0o755)
    log(f"Launcher berhasil dikompilasi ke {target_exe}")


def write_info_plist():
    log("Menulis Info.plist...")
    template_path = os.path.join(ROOT_DIR, "launcher", "Info.plist.template")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    version = "2.10.0"
    ver_path = os.path.join(ROOT_DIR, "VERSION")
    if os.path.exists(ver_path):
        with open(ver_path, "r", encoding="utf-8") as f:
            version = f.read().strip()

    content = content.replace("{VERSION}", version)
    plist_path = os.path.join(CONTENTS_DIR, "Info.plist")
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(content)


def codesign_bundle():
    log("Melakukan ad-hoc code signing pada Tatap.app...")
    subprocess.run(["codesign", "--deep", "--force", "--verify", "--verbose", "--sign", "-", APP_DIR], check=True)
    log("Code sign selesai.")


def main():
    log("=== Memulai Build macOS app bundle (arm64) ===")
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(MACOS_DIR, exist_ok=True)
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    setup_standalone_python()
    install_dependencies()
    copy_project_files()
    prepare_icon()
    build_launcher()
    write_info_plist()
    codesign_bundle()

    size_mb = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, filenames in os.walk(APP_DIR) for f in filenames) / (1024 * 1024)
    log(f"=== Build macOS app selesai: {APP_DIR} ({size_mb:.2f} MB) ===")


if __name__ == "__main__":
    main()
