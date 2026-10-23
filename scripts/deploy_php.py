#!/usr/bin/env python
"""
Deploy PHP files to IONOS hosting via SFTP.
"""

import paramiko
import os

# SFTP credentials (from environment - see config/secrets.env)
HOST = os.environ.get('IONOS_SFTP_HOST', '')
PORT = int(os.environ.get('IONOS_SFTP_PORT', '22'))
USER = os.environ.get('IONOS_SFTP_USER', '')
PASSWORD = os.environ.get('SFTP_PASSWORD', '')

# Local files
LOCAL_DB = os.path.join(os.path.dirname(__file__), 'api', 'db.php')
LOCAL_TRACK = os.path.join(os.path.dirname(__file__), 'api', 'track.php')

# Remote directory
REMOTE_DIR = '/gapfeed.com/api/'

def deploy():
    print(f"Connecting to {HOST}:{PORT} as {USER}...")
    transport = paramiko.Transport((HOST, PORT))
    transport.connect(username=USER, password=PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    try:
        # Ensure remote directory exists (SFTP may not have mkdir)
        # Upload db.php
        remote_db = REMOTE_DIR + 'db.php'
        print(f"Uploading {LOCAL_DB} to {remote_db}")
        sftp.put(LOCAL_DB, remote_db)
        print("  OK")
        
        # Upload track.php
        remote_track = REMOTE_DIR + 'track.php'
        print(f"Uploading {LOCAL_TRACK} to {remote_track}")
        sftp.put(LOCAL_TRACK, remote_track)
        print("  OK")
        
        # Upload test_input.php
        local_test = os.path.join(os.path.dirname(__file__), 'api', 'test_input.php')
        remote_test = REMOTE_DIR + 'test_input.php'
        print(f"Uploading {local_test} to {remote_test}")
        sftp.put(local_test, remote_test)
        print("  OK")
        
        print("\nDeployment completed successfully.")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        sftp.close()
        transport.close()

if __name__ == '__main__':
    deploy()