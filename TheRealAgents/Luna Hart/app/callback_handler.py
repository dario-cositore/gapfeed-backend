#!/usr/bin/env python3
"""
Luna Hart - Telegram Callback Handler
Listens for approve/reject button taps and updates pending_approval.json
Run this alongside the main agent.
"""
import json
import os
import sys
import time
import requests
from pathlib import Path

# Config
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "base.json"
PENDING_PATH = Path(__file__).resolve().parent.parent / "memory" / "pending_approval.json"

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def load_pending():
    if os.path.exists(PENDING_PATH):
        with open(PENDING_PATH, 'r') as f:
            return json.load(f)
    return {"drafts": []}

def save_pending(data):
    os.makedirs(os.path.dirname(PENDING_PATH), exist_ok=True)
    with open(PENDING_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def handle_callback(callback_data, callback_query_id, bot_token):
    """Process a callback query from inline buttons."""
    print(f"Callback received: {callback_data}")

    if callback_data.startswith("blog_approve_"):
        draft_id = callback_data[13:]  # Remove "blog_approve_" prefix
        pending = load_pending()

        for draft in pending.get("drafts", []):
            if draft.get("id") == draft_id:
                draft["status"] = "approved"
                draft["approved_at"] = __import__("datetime").datetime.now().isoformat()
                print(f"Blog draft approved: {draft_id}")
                break

        save_pending(pending)

        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": "Blog approved! Will be deployed to dariocositore.com."
        }, timeout=10)

    elif callback_data.startswith("blog_reject_"):
        draft_id = callback_data[12:]  # Remove "blog_reject_" prefix
        pending = load_pending()

        for draft in pending.get("drafts", []):
            if draft.get("id") == draft_id:
                draft["status"] = "rejected"
                draft["rejected_at"] = __import__("datetime").datetime.now().isoformat()
                print(f"Blog draft rejected: {draft_id}")
                break

        save_pending(pending)

        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": "Blog draft rejected."
        }, timeout=10)

    elif callback_data.startswith("approve_"):
        draft_id = callback_data[8:]  # Remove "approve_" prefix
        pending = load_pending()

        for draft in pending.get("drafts", []):
            if draft.get("id") == draft_id:
                draft["status"] = "approved"
                draft["approved_at"] = __import__("datetime").datetime.now().isoformat()
                print(f"Draft approved: {draft_id}")
                break

        save_pending(pending)

        # Answer callback with confirmation
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": "Draft approved! Will be scheduled."
        }, timeout=10)

    elif callback_data.startswith("reject_"):
        draft_id = callback_data[7:]  # Remove "reject_" prefix
        pending = load_pending()

        for draft in pending.get("drafts", []):
            if draft.get("id") == draft_id:
                draft["status"] = "rejected"
                draft["rejected_at"] = __import__("datetime").datetime.now().isoformat()
                print(f"Draft rejected: {draft_id}")
                break

        save_pending(pending)

        # Answer callback with confirmation
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": "Draft rejected."
        }, timeout=10)

def poll_updates(bot_token, last_update_id):
    """Poll Telegram for new updates."""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 10}
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    
                    if "callback_query" in update:
                        callback = update["callback_query"]
                        callback_data = callback.get("data", "")
                        callback_id = callback.get("id", "")
                        
                        if callback_data.startswith(("approve_", "reject_", "blog_approve_", "blog_reject_")):
                            handle_callback(callback_data, callback_id, bot_token)
    except Exception as e:
        print(f"Poll error: {e}")
    
    return last_update_id

def main():
    print("=== Luna Hart Callback Handler ===")
    print("Listening for approve/reject button taps...")
    
    config = load_config()
    bot_token = config.get("telegram", {}).get("bot_token")
    
    if not bot_token:
        print("ERROR: No bot token in config")
        sys.exit(1)
    
    last_update_id = 0
    
    while True:
        try:
            last_update_id = poll_updates(bot_token, last_update_id)
            time.sleep(1)  # Poll every second
        except KeyboardInterrupt:
            print("\nShutting down callback handler.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
