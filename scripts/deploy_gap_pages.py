#!/usr/bin/env python3
"""Deploy gapfeed.com static pages to IONOS hosting.

Uploads gap pages, categories, sources, tags, robots.txt, sitemap.xml.
Skips existing index.html and _staging/ (not our domain).
"""

import paramiko
import os
from pathlib import Path

# Config (from environment - see config/secrets.env)
HOST = os.environ.get("IONOS_SFTP_HOST", "")
PORT = int(os.environ.get("IONOS_SFTP_PORT", "22"))
USERNAME = os.environ.get("IONOS_SFTP_USER", "")
PASSWORD = os.environ.get("SFTP_PASSWORD", "")

LOCAL_DIR = Path(__file__).resolve().parent.parent / "website" / "gapfeed.com"
REMOTE_DIR = "/gapfeed.com"

# Only deploy these directories and files
DEPLOY_ITEMS = {
    "gap", "categories", "sources", "tags",
    "robots.txt", "sitemap.xml"
}

def upload_file(sftp, local_path, remote_path):
    """Upload a single file."""
    remote_parent = os.path.dirname(remote_path)
    try:
        sftp.mkdir(remote_parent)
    except IOError:
        pass
    print(f"  {local_path} -> {remote_path}")
    sftp.put(str(local_path), remote_path)

def upload_recursive(sftp, local_dir, remote_dir):
    """Recursively upload directory."""
    for item in os.listdir(local_dir):
        local_path = local_dir / item
        remote_path = f"{remote_dir}/{item}"

        if local_path.is_dir():
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass
            upload_recursive(sftp, local_path, remote_path)
        else:
            upload_file(sftp, local_path, remote_path)

def main():
    print(f"Deploying gapfeed.com static pages to {HOST}:{REMOTE_DIR}")
    print(f"Local source: {LOCAL_DIR}")
    print()

    ssh = paramiko.Transport((HOST, PORT))
    ssh.connect(username=USERNAME, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(ssh)

    try:
        sftp.chdir(REMOTE_DIR)
    except IOError:
        print(f"ERROR: Remote directory {REMOTE_DIR} does not exist!")
        ssh.close()
        return

    uploaded = 0

    for item in DEPLOY_ITEMS:
        local_path = LOCAL_DIR / item
        remote_path = f"{REMOTE_DIR}/{item}"

        if not local_path.exists():
            print(f"  SKIP (not found): {item}")
            continue

        if local_path.is_dir():
            print(f"\n=== Uploading {item}/ ===")
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass

            count_before = uploaded
            for root, dirs, files in os.walk(local_path):
                rel = os.path.relpath(root, local_path)
                if rel == ".":
                    remote_root = remote_path
                else:
                    remote_root = f"{remote_path}/{rel.replace(os.sep, '/')}"

                for d in dirs:
                    try:
                        sftp.mkdir(f"{remote_root}/{d}")
                    except IOError:
                        pass

                for f in files:
                    lp = os.path.join(root, f)
                    rp = f"{remote_root}/{f}"
                    upload_file(sftp, lp, rp)
                    uploaded += 1

            print(f"  {uploaded - count_before} files in {item}/")
        else:
            print(f"\n=== Uploading {item} ===")
            upload_file(sftp, local_path, remote_path)
            uploaded += 1

    print(f"\nDeploy complete! {uploaded} files uploaded.")

    sftp.close()
    ssh.close()

if __name__ == "__main__":
    main()
