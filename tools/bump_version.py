#!/usr/bin/env python3
"""
Tatap Semantic Versioning 2.0.0 Manager
---------------------------------------
Utilitas standar untuk memeriksa, memvalidasi, dan menaikkan versi
aplikasi Tatap secara atomik di seluruh ekosistem multiplatform.

Penggunaan:
    python3 tools/bump_version.py patch       # Naikkan PATCH (misal 2.3.0 -> 2.3.1)
    python3 tools/bump_version.py minor       # Naikkan MINOR (misal 2.3.0 -> 2.4.0, patch reset ke 0)
    python3 tools/bump_version.py major       # Naikkan MAJOR (misal 2.3.0 -> 3.0.0, minor & patch reset ke 0)
    python3 tools/bump_version.py 2.4.0       # Tetapkan versi spesifik
    python3 tools/bump_version.py --check     # Periksa konsistensi seluruh berkas (CI Audit)
    python3 tools/bump_version.py --sync-readme [VERSION] # Sinkronkan tautan download README ke versi rilis publik
"""

import sys
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT_DIR, "VERSION")
BACKEND_VER_FILE = os.path.join(ROOT_DIR, "backend", "version.py")
ANDROID_VER_FILE = os.path.join(ROOT_DIR, "android", "app", "src", "main", "python", "backend", "version.py")
WINRES_FILE = os.path.join(ROOT_DIR, "launcher", "winres", "winres.json")
MANIFEST_FILE = os.path.join(ROOT_DIR, "launcher", "winres", "tatap.manifest")
FRONTEND_HTML = os.path.join(ROOT_DIR, "frontend", "index.html")
README_FILE = os.path.join(ROOT_DIR, "README.md")

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def get_current_version() -> str:
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    return "2.3.0"


def parse_semver(v_str: str):
    m = SEMVER_REGEX.match(v_str.strip())
    if not m:
        raise ValueError(f"String '{v_str}' tidak mematuhi spesifikasi resmi Semantic Versioning 2.0.0!")
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    prerelease = m.group(4)
    buildmeta = m.group(5)
    return major, minor, patch, prerelease, buildmeta


def calculate_version_code(v_str: str) -> int:
    major, minor, patch, _, _ = parse_semver(v_str)
    return (major * 10000) + (minor * 100) + patch


def bump(category: str, current: str) -> str:
    major, minor, patch, _, _ = parse_semver(current)
    cat = category.lower().strip()
    if cat == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif cat == "minor":
        return f"{major}.{minor + 1}.0"
    elif cat == "major":
        return f"{major + 1}.0.0"
    elif SEMVER_REGEX.match(category.strip()):
        return category.strip()
    else:
        raise ValueError(f"Kategori tidak dikenal: '{category}'. Gunakan 'patch', 'minor', 'major', atau nomor versi SemVer (misal: 2.3.1).")


def update_file(path: str, transform_fn):
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = transform_fn(content)
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


def sync_readme_version(version: str) -> bool:
    parse_semver(version)
    def repl_readme(content: str) -> str:
        content = re.sub(r'tatap-release-v[0-9.]+\.apk', f'tatap-release-v{version}.apk', content)
        content = re.sub(r'tatap-tv-release-v[0-9.]+\.apk', f'tatap-tv-release-v{version}.apk', content)
        content = re.sub(r'tatap-macos-[0-9.]+-arm64\.dmg', f'tatap-macos-{version}-arm64.dmg', content)
        return content
    updated = update_file(README_FILE, repl_readme)
    if updated:
        print(f" ✓ {os.path.relpath(README_FILE, ROOT_DIR)} -> v{version}")
    else:
        print(f"   {os.path.relpath(README_FILE, ROOT_DIR)} sudah memuat v{version}")
    return updated


def apply_version(new_version: str, sync_readme: bool = False):
    parse_semver(new_version) # validasi
    win_version = f"{new_version}.0"

    print(f"\n🚀 [SEMVER] Memperbarui aplikasi Tatap ke v{new_version}")
    print(f"   Android versionCode: {calculate_version_code(new_version)}")
    print("------------------------------------------------------------")

    # 1. Root VERSION
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(f"{new_version}\n")
    print(f" ✓ {os.path.relpath(VERSION_FILE, ROOT_DIR)} -> {new_version}")

    # 2. backend/version.py & Chaquopy
    ver_py_content = f'# Single source of truth version for Tatap backend\n# Synchronized with root VERSION file by tools/bump_version.py\n\n__version__ = "{new_version}"\n'
    for p in (BACKEND_VER_FILE, ANDROID_VER_FILE):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(ver_py_content)
        print(f" ✓ {os.path.relpath(p, ROOT_DIR)} -> __version__ = \"{new_version}\"")

    # 3. launcher/winres/winres.json
    def repl_winres(content: str) -> str:
        content = re.sub(r'"file_version":\s*"[^"]+"', f'"file_version": "{win_version}"', content)
        content = re.sub(r'"product_version":\s*"[^"]+"', f'"product_version": "{win_version}"', content)
        content = re.sub(r'"FileVersion":\s*"[^"]+"', f'"FileVersion": "{win_version}"', content)
        content = re.sub(r'"ProductVersion":\s*"[^"]+"', f'"ProductVersion": "{win_version}"', content)
        return content
    update_file(WINRES_FILE, repl_winres)
    print(f" ✓ {os.path.relpath(WINRES_FILE, ROOT_DIR)} -> {win_version}")

    # 4. launcher/winres/tatap.manifest
    def repl_manifest(content: str) -> str:
        return re.sub(r'<assemblyIdentity\s+version="[^"]+"', f'<assemblyIdentity version="{win_version}"', content)
    update_file(MANIFEST_FILE, repl_manifest)
    print(f" ✓ {os.path.relpath(MANIFEST_FILE, ROOT_DIR)} -> {win_version}")

    # 5. frontend/index.html (Badge versi)
    def repl_html(content: str) -> str:
        content = re.sub(r'<span class="brand-ver" id="brand-ver">v[^<]+</span>', f'<span class="brand-ver" id="brand-ver">v{new_version}</span>', content)
        content = re.sub(r'<span class="dim small">v[^<]+</span>', f'<span class="dim small">v{new_version}</span>', content)
        return content
    update_file(FRONTEND_HTML, repl_html)
    print(f" ✓ {os.path.relpath(FRONTEND_HTML, ROOT_DIR)} -> v{new_version}")

    # 6. README.md (Download links)
    if sync_readme:
        sync_readme_version(new_version)
    else:
        print(f" ℹ {os.path.relpath(README_FILE, ROOT_DIR)}: tautan unduhan tetap mengarah ke latest public release.")
        print(f"   (Jalankan 'python3 tools/bump_version.py --sync-readme' setelah rilis resmi dipublikasikan).")

    print("------------------------------------------------------------")
    print("✅ Berhasil menstandarkan versi di seluruh modul!")
    print(f"\nLangkah berikutnya:")
    print(f"  git commit -am 'chore(release): bump to v{new_version}'")
    print(f"  git tag -a v{new_version} -m 'Release v{new_version}'")


def check_consistency():
    curr = get_current_version()
    print(f"[AUDIT] Memeriksa konsistensi versi SemVer Tatap (Root: {curr})...")
    errors = []

    try:
        parse_semver(curr)
        print(f" ✓ File VERSION: '{curr}' (Valid SemVer 2.0.0)")
    except Exception as e:
        errors.append(f"File VERSION tidak valid: {e}")

    # backend/version.py
    if os.path.exists(BACKEND_VER_FILE):
        with open(BACKEND_VER_FILE, "r", encoding="utf-8") as f:
            c = f.read()
            m = re.search(r'__version__\s*=\s*"([^"]+)"', c)
            if not m or m.group(1) != curr:
                errors.append(f"backend/version.py ({m.group(1) if m else 'N/A'}) tidak cocok dengan VERSION ({curr})")
            else:
                print(f" ✓ backend/version.py: '{m.group(1)}'")

    # android version.py
    if os.path.exists(ANDROID_VER_FILE):
        with open(ANDROID_VER_FILE, "r", encoding="utf-8") as f:
            c = f.read()
            m = re.search(r'__version__\s*=\s*"([^"]+)"', c)
            if not m or m.group(1) != curr:
                errors.append(f"android backend version.py ({m.group(1) if m else 'N/A'}) tidak cocok dengan VERSION ({curr})")
            else:
                print(f" ✓ android/app/.../backend/version.py: '{m.group(1)}'")

    # launcher winres.json
    win_exp = f"{curr}.0"
    if os.path.exists(WINRES_FILE):
        with open(WINRES_FILE, "r", encoding="utf-8") as f:
            c = f.read()
            if f'"{win_exp}"' not in c:
                errors.append(f"launcher/winres/winres.json tidak memuat '{win_exp}'")
            else:
                print(f" ✓ launcher/winres/winres.json: '{win_exp}'")

    # frontend/index.html
    if os.path.exists(FRONTEND_HTML):
        with open(FRONTEND_HTML, "r", encoding="utf-8") as f:
            c = f.read()
            if f'v{curr}' not in c:
                errors.append(f"frontend/index.html tidak memuat 'v{curr}'")
            else:
                print(f" ✓ frontend/index.html: 'v{curr}'")

    # README.md (Harus mengarah ke versi SemVer valid yang <= curr, merefleksikan latest public release)
    if os.path.exists(README_FILE):
        with open(README_FILE, "r", encoding="utf-8") as f:
            c = f.read()
            m1 = re.search(r'tatap-release-v([0-9.]+)\.apk', c)
            m2 = re.search(r'tatap-tv-release-v([0-9.]+)\.apk', c)
            if not m1 or not m2 or m1.group(1) != m2.group(1):
                errors.append(f"README.md download links tidak konsisten ({m1.group(1) if m1 else 'N/A'} vs {m2.group(1) if m2 else 'N/A'})")
            else:
                readme_ver = m1.group(1)
                try:
                    parse_semver(readme_ver)
                    curr_code = calculate_version_code(curr)
                    readme_code = calculate_version_code(readme_ver)
                    if readme_code > curr_code:
                        errors.append(f"README.md memuat versi v{readme_ver} yang lebih tinggi dari VERSION v{curr}!")
                    else:
                        status_tag = "Latest Public" if readme_code < curr_code else "Synchronized"
                        print(f" ✓ README.md: download links 'v{readme_ver}' ({status_tag})")
                except Exception as e:
                    errors.append(f"README.md download links memuat versi tidak valid: {e}")

    if errors:
        print("\n❌ Terdeteksi ketidakkonsistenan versi:")
        for err in errors:
            print(f"   - {err}")
        sys.exit(1)
    else:
        print("\n🎉 Seluruh berkas 100% konsisten dengan standar SemVer 2.0.0!")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    arg = sys.argv[1].strip()
    if arg == "--check":
        check_consistency()
        sys.exit(0)

    if arg == "--sync-readme":
        target_v = sys.argv[2].strip() if len(sys.argv) > 2 else get_current_version()
        sync_readme_version(target_v)
        sys.exit(0)

    sync_readme = "--sync-readme" in sys.argv[2:]
    curr = get_current_version()
    new_v = bump(arg, curr)
    apply_version(new_v, sync_readme=sync_readme)


if __name__ == "__main__":
    main()
