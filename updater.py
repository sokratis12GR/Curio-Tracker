import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# ======================
GITHUB_OWNER = "sokratis12GR"
GITHUB_REPO = "Curio-Tracker"
APP_NAME = "Heist Curio Tracker.exe"
EXPECTED_SIGNER = "Sokratis Fotkatzikis"
# ======================

def wait_for_app_to_close(app_path):
    while True:
        try:
            os.rename(app_path, app_path)
            break
        except PermissionError:
            time.sleep(0.5)


def get_latest_release():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def download_file(url, dest_path):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


def verify_signature(file_path):
    import subprocess
    command = ["powershell", "-Command", f"(Get-AuthenticodeSignature '{file_path}').SignerCertificate.Subject"]
    result = subprocess.run(command, capture_output=True, text=True)
    print("PowerShell return code:", result.returncode)
    print("stdout:", result.stdout)
    print("stderr:", result.stderr)
    if result.returncode != 0:
        return False
    return EXPECTED_SIGNER in result.stdout.strip()


def main():
    base_dir = Path(sys.executable).parent
    app_path = base_dir / APP_NAME

    temp_file = base_dir / "update_tmp.exe"

    try:
        release = get_latest_release()
    except Exception as e:
        print(f"[ERROR] Failed to fetch release info: {e}")
        return

    exe_url = None
    for asset in release.get("assets", []):
        name = asset["name"].lower()
        if name == "heist.curio.tracker.exe":
            exe_url = asset["browser_download_url"]
            break

    if not exe_url:
        print("No matching exe found in release. Assets:", [a["name"] for a in release.get("assets", [])])
        return

    print("[INFO] Downloading latest version...")
    try:
        download_file(exe_url, temp_file)
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        return

    print("[INFO] Verifying digital signature...")
    if not verify_signature(temp_file):
        print("[ERROR] Signature verification failed! Aborting update.")
        temp_file.unlink(missing_ok=True)
        return
    print("[INFO] Signature verified successfully.")

    print("[INFO] Waiting for app to close...")
    wait_for_app_to_close(app_path)

    print("[INFO] Replacing executable...")
    try:
        os.replace(temp_file, app_path)
    except Exception as e:
        print(f"[ERROR] Failed to replace executable: {e}")
        return

    print("[INFO] Restarting application...")
    subprocess.Popen([str(app_path)])
    print("[INFO] Update complete.")


if __name__ == "__main__":
    main()
