#!/usr/bin/env python3
"""
Post welcome/rules embeds to the server. Run once after setup.

Usage: python welcome.py --token BOT_TOKEN --guild SERVER_ID
"""

import argparse
import requests
import time

API = "https://discord.com/api/v10"


def headers(token):
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


def find_channel(token, guild_id, name):
    channels = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers(token)).json()
    for ch in channels:
        if ch["name"] == name:
            return ch["id"]
    return None


def post_embed(token, channel_id, embed):
    r = requests.post(
        f"{API}/channels/{channel_id}/messages",
        headers=headers(token),
        json={"embeds": [embed]},
    )
    if r.status_code == 429:
        time.sleep(r.json().get("retry_after", 1) + 0.5)
        return post_embed(token, channel_id, embed)
    r.raise_for_status()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--guild", required=True)
    args = parser.parse_args()

    # --- #rules ---
    rules_id = find_channel(args.token, args.guild, "rules")
    if rules_id:
        post_embed(args.token, rules_id, {
            "title": "Walking the Planck",
            "description": (
                "Physics simulation from first principles.\n\n"
                "We build open-source tools for physically accurate voxel simulation — "
                "from atomic chemistry to fluid dynamics.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            "color": 0x3498db,
            "fields": [
                {
                    "name": "Our Projects",
                    "value": (
                        "**Hyle** — Headless voxel simulation engine with LBM fluid solver\n"
                        "**Materia** — Chemical composition → material properties ([crates.io](https://crates.io/crates/materia))\n"
                        "**Burst** — Voxel game engine powered by Hyle"
                    ),
                    "inline": False,
                },
                {
                    "name": "Links",
                    "value": (
                        "[GitHub](https://github.com/walkingtheplanck) · "
                        "[Materia on crates.io](https://crates.io/crates/materia)"
                    ),
                    "inline": False,
                },
            ],
            "footer": {"text": "Welcome aboard."},
        })
        print("Posted welcome embed to #rules")

        post_embed(args.token, rules_id, {
            "title": "Server Rules",
            "color": 0xe74c3c,
            "fields": [
                {"name": "1. Be respectful", "value": "Treat everyone with courtesy. No harassment, hate speech, or personal attacks.", "inline": False},
                {"name": "2. Stay on topic", "value": "Use the right channel for your discussion. Keep #general casual and project channels technical.", "inline": False},
                {"name": "3. No spam", "value": "No repeated messages, unsolicited promotions, or bot abuse.", "inline": False},
                {"name": "4. Share knowledge", "value": "This is a learning community. Ask questions freely, help others when you can.", "inline": False},
                {"name": "5. Credit your sources", "value": "When sharing code or ideas from others, give proper attribution.", "inline": False},
            ],
            "footer": {"text": "Breaking rules may result in a warning, mute, or ban."},
        })
        print("Posted rules embed to #rules")

    # --- #roadmap ---
    roadmap_id = find_channel(args.token, args.guild, "roadmap")
    if roadmap_id:
        post_embed(args.token, roadmap_id, {
            "title": "Roadmap",
            "description": "Current priorities and what's coming next.",
            "color": 0x2ecc71,
            "fields": [
                {
                    "name": "Hyle — Voxel Simulation Engine",
                    "value": (
                        "✅ D3Q19 LBM solver (validated: Poiseuille, diffusion, convergence)\n"
                        "✅ MRT collision operator\n"
                        "✅ VOF free-surface tracking (100% mass conservation)\n"
                        "✅ Material-aware movement (water flattens, sand piles)\n"
                        "✅ GPU compute DDA raytracer\n"
                        "🔄 VOF absorption (fluid → substrate saturation)\n"
                        "🔲 GPU LBM compute shader\n"
                        "🔲 Wind simulation + vegetation interaction"
                    ),
                    "inline": False,
                },
                {
                    "name": "Materia — Chemistry Library",
                    "value": (
                        "✅ 118 elements with real atomic data\n"
                        "✅ 10+ physics models (Dulong-Petit, Wiedemann-Franz, etc.)\n"
                        "✅ 13 chemical reactions with energy balance\n"
                        "✅ 20 preset world materials\n"
                        "✅ Published on crates.io\n"
                        "🔲 More reactions and estimation model refinements"
                    ),
                    "inline": False,
                },
            ],
            "footer": {"text": "Updated manually. Check GitHub for latest."},
        })
        print("Posted roadmap embed to #roadmap")


if __name__ == "__main__":
    main()
