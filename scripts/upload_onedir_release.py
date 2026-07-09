#!/usr/bin/env python3
"""Upload zip, patch, installer, and version.json to GitLab Package Registry."""

import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://10.8.251.3:8081"
PROJECT = "design/LuxeLead"
PID = 220
MANIFEST = ROOT / "releases" / "version.json"
RELEASE_DIR = ROOT / "dist" / "release"


def git_login():
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=http\nhost=10.8.251.3:8081\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    cred = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            cred[key] = value
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    html = opener.open(BASE + "/users/sign_in").read().decode("utf-8", "replace")
    tok = re.search(r'name="authenticity_token" value="([^"]+)"', html).group(1)
    data = urllib.parse.urlencode(
        {
            "authenticity_token": tok,
            "user[login]": cred["username"],
            "user[password]": cred["password"],
            "user[remember_me]": "0",
        }
    ).encode()
    opener.open(
        urllib.request.Request(
            BASE + "/users/sign_in",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    )
    page = opener.open(BASE + "/" + PROJECT).read().decode("utf-8", "replace")
    csrf = re.search(r'csrf-token" content="([^"]+)"', page).group(1)
    return opener, csrf


def upload_bytes(opener, csrf, package: str, version: str, filename: str, body: bytes) -> None:
    url = f"{BASE}/api/v4/projects/{PID}/packages/generic/{package}/{version}/{filename}"
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Content-Type": "application/octet-stream",
            "X-CSRF-Token": csrf,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with opener.open(req, timeout=900) as resp:
        print(f"[OK] upload {package}/{version}/{filename} HTTP {resp.status} ({len(body)//1024//1024} MB)")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Upload release artifacts to GitLab")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Only upload version.json (skip zip/patch/installer)",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = manifest["version"]
    opener, csrf = git_login()

    uploads = []
    if not args.manifest_only:
        zip_path = RELEASE_DIR / manifest["filename"]
        if zip_path.is_file():
            uploads.append(("luxelead", version, manifest["filename"], zip_path))

        for patch in manifest.get("patches") or []:
            patch_path = RELEASE_DIR / patch["filename"]
            if patch_path.is_file():
                uploads.append(("luxelead", version, patch["filename"], patch_path))

        installer = manifest.get("installer") or {}
        if installer.get("filename"):
            setup_path = RELEASE_DIR / installer["filename"]
            if setup_path.is_file():
                uploads.append(("luxelead", version, installer["filename"], setup_path))

    if not uploads and not args.manifest_only:
        print("[ERROR] 未找到任何待上传文件", file=sys.stderr)
        return 1

    for idx, (package, pkg_version, filename, path) in enumerate(uploads, start=1):
        print(f"[{idx}/{len(uploads)}] Uploading {filename}...")
        upload_bytes(opener, csrf, package, pkg_version, filename, path.read_bytes())

    body = MANIFEST.read_bytes()
    print("[manifest] Uploading version.json...")
    upload_bytes(opener, csrf, "luxelead-manifest", version, "version.json", body)
    upload_bytes(opener, csrf, "luxelead-manifest", "latest", "version.json", body)

    token = manifest.get("download_token", "")
    if not token:
        print("[WARN] version.json 缺少 download_token，跳过远程校验")
        return 0

    req = urllib.request.Request(
        f"{BASE}/api/v4/projects/{PID}/packages/generic/luxelead-manifest/latest/version.json",
        headers={"DEPLOY-TOKEN": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            remote = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"[WARN] 远程校验失败: HTTP {exc.code}", file=sys.stderr)
        return 0
    print(f"[OK] remote version={remote.get('version')} patches={len(remote.get('patches') or [])}")
    if remote.get("installer"):
        print(f"[OK] installer={remote['installer'].get('filename')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
