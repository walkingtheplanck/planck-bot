#!/usr/bin/env python3
"""
Apply a Discord server template from JSON via the Discord REST API.

Usage:
    1. Create a bot at https://discord.com/developers/applications
    2. Enable Server Members Intent + Message Content Intent
    3. Invite bot to your server with admin permissions:
       https://discord.com/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=8&scope=bot
    4. Run: python setup.py --token YOUR_BOT_TOKEN --guild YOUR_SERVER_ID --template template.json

The script will:
    - Create roles (skips if already exist)
    - Create categories and channels (skips if already exist)
    - Set read-only permissions on channels marked readonly
    - Set channel topics
"""

import argparse
import json
import time
import requests

API = "https://discord.com/api/v10"


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }


def api_get(token: str, path: str):
    r = requests.get(f"{API}{path}", headers=headers(token))
    if r.status_code == 401:
        print(f"ERROR: Invalid bot token. Check DISCORD_BOT_TOKEN secret.")
        exit(1)
    if r.status_code == 403:
        print(f"ERROR: Bot lacks permissions. Invite with Administrator permission.")
        exit(1)
    if r.status_code == 404:
        print(f"ERROR: Guild not found. Either DISCORD_GUILD_ID is wrong or the bot isn't in the server.")
        print(f"  1. Right-click your server name in Discord -> Copy Server ID")
        print(f"  2. Make sure the bot is invited to that server")
        exit(1)
    r.raise_for_status()
    return r.json()


def api_post(token: str, path: str, data: dict):
    r = requests.post(f"{API}{path}", headers=headers(token), json=data)
    if r.status_code == 429:
        retry = r.json().get("retry_after", 1)
        print(f"  Rate limited, waiting {retry:.1f}s...")
        time.sleep(retry + 0.5)
        return api_post(token, path, data)
    if r.status_code >= 400:
        import sys
        print(f"  API ERROR {r.status_code}: {r.text}", file=sys.stderr, flush=True)
        print(f"  Request data: {json.dumps(data)}", file=sys.stderr, flush=True)
        sys.exit(1)
    return r.json()


def api_patch(token: str, path: str, data: dict):
    r = requests.patch(f"{API}{path}", headers=headers(token), json=data)
    if r.status_code == 429:
        retry = r.json().get("retry_after", 1)
        time.sleep(retry + 0.5)
        return api_patch(token, path, data)
    r.raise_for_status()
    return r.json()


def find_by_name(items: list, name: str):
    for item in items:
        if item["name"] == name:
            return item
    return None


def hex_to_int(hex_color: str) -> int:
    return int(hex_color.lstrip("#"), 16)


def create_roles(token: str, guild_id: str, roles: list):
    existing = api_get(token, f"/guilds/{guild_id}/roles")
    created = {}

    for role_def in roles:
        name = role_def["name"]
        existing_role = find_by_name(existing, name)

        if existing_role:
            print(f"  Role '{name}' already exists, skipping.")
            created[name] = existing_role["id"]
            continue

        data = {
            "name": name,
            "color": hex_to_int(role_def.get("color", "#000000")),
            "permissions": role_def.get("permissions", "0"),
        }
        result = api_post(token, f"/guilds/{guild_id}/roles", data)
        created[name] = result["id"]
        print(f"  Created role: {name}")
        time.sleep(0.5)

    return created


def create_channels(token: str, guild_id: str, categories: list):
    existing = api_get(token, f"/guilds/{guild_id}/channels")
    everyone_role = None

    # Find @everyone role (same ID as guild)
    roles = api_get(token, f"/guilds/{guild_id}/roles")
    for r in roles:
        if r["name"] == "@everyone":
            everyone_role = r["id"]
            break

    for cat_def in categories:
        cat_name = cat_def["name"]
        existing_cat = None

        # Check if category exists
        for ch in existing:
            if ch["name"] == cat_name and ch["type"] == 4:
                existing_cat = ch
                break

        if existing_cat:
            cat_id = existing_cat["id"]
            print(f"  Category '{cat_name}' already exists.")
        else:
            result = api_post(token, f"/guilds/{guild_id}/channels", {
                "name": cat_name,
                "type": 4,  # GUILD_CATEGORY
            })
            cat_id = result["id"]
            print(f"  Created category: {cat_name}")
            time.sleep(0.5)

        # Refresh existing channels after category creation
        existing = api_get(token, f"/guilds/{guild_id}/channels")

        for ch_def in cat_def.get("channels", []):
            ch_name = ch_def["name"]

            # Check if channel exists in this category
            ch_exists = False
            for ch in existing:
                if ch["name"] == ch_name and ch.get("parent_id") == cat_id:
                    ch_exists = True
                    print(f"    Channel '#{ch_name}' already exists, skipping.")
                    break

            if ch_exists:
                continue

            # Permission overrides for readonly channels
            overrides = []
            if ch_def.get("readonly", False) and everyone_role:
                overrides.append({
                    "id": everyone_role,
                    "type": 0,  # role
                    "deny": str(1 << 11),  # SEND_MESSAGES
                    "allow": "0",
                })

            # Channel type: 0=text, 5=announcement, 15=forum
            ch_type = ch_def.get("type", 0)

            data = {
                "name": ch_name,
                "type": ch_type,
                "parent_id": cat_id,
                "topic": ch_def.get("topic", ""),
                "permission_overwrites": overrides,
            }
            api_post(token, f"/guilds/{guild_id}/channels", data)
            type_label = {0: "", 5: " (announcement)", 15: " (forum)"}.get(ch_type, "")
            print(f"    Created #{ch_name}" + type_label + (" [read-only]" if ch_def.get("readonly") else ""))
            time.sleep(0.5)


def reset_server(token: str, guild_id: str):
    """Delete ALL non-default channels and roles, then re-apply template."""
    print("RESETTING SERVER — deleting all channels and custom roles...")
    print()

    # Delete all channels
    channels = api_get(token, f"/guilds/{guild_id}/channels")
    for ch in channels:
        try:
            r = requests.delete(f"{API}/channels/{ch['id']}", headers=headers(token))
            if r.status_code == 429:
                time.sleep(r.json().get("retry_after", 1) + 0.5)
                requests.delete(f"{API}/channels/{ch['id']}", headers=headers(token))
            print(f"  Deleted #{ch['name']}")
            time.sleep(0.3)
        except Exception as e:
            print(f"  Failed to delete #{ch['name']}: {e}")

    # Delete custom roles (skip @everyone and bot-managed roles)
    roles = api_get(token, f"/guilds/{guild_id}/roles")
    for role in roles:
        if role["name"] == "@everyone" or role.get("managed", False):
            continue
        try:
            r = requests.delete(f"{API}/guilds/{guild_id}/roles/{role['id']}", headers=headers(token))
            if r.status_code == 429:
                time.sleep(r.json().get("retry_after", 1) + 0.5)
                requests.delete(f"{API}/guilds/{guild_id}/roles/{role['id']}", headers=headers(token))
            print(f"  Deleted role: {role['name']}")
            time.sleep(0.3)
        except Exception as e:
            print(f"  Failed to delete role {role['name']}: {e}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Apply Discord server template from JSON.")
    parser.add_argument("--token", required=True, help="Discord bot token")
    parser.add_argument("--guild", required=True, help="Discord server (guild) ID")
    parser.add_argument("--template", default="template.json", help="Path to template JSON")
    parser.add_argument("--reset", action="store_true", help="Delete all channels/roles before applying")
    args = parser.parse_args()

    with open(args.template) as f:
        template = json.load(f)

    print(f"Applying template to guild {args.guild}...")
    print()

    if args.reset:
        reset_server(args.token, args.guild)

    print("Creating roles...")
    roles = create_roles(args.token, args.guild, template.get("roles", []))
    print()

    print("Creating channels...")
    create_channels(args.token, args.guild, template.get("categories", []))
    print()

    print("Done! Server structure applied.")


if __name__ == "__main__":
    main()
