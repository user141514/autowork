from __future__ import annotations

import argparse
import json
import os


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike: read recent messages from a whitelisted WeChat group via wxauto.")
    parser.add_argument("--room", required=True, help="Exact whitelisted group name.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("AGENT_WORKFLOW_WECHAT_READ_LIMIT", "20")))
    args = parser.parse_args()

    allowed_rooms = {
        room.strip()
        for room in os.getenv("AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS", "").split(",")
        if room.strip()
    }
    if args.room not in allowed_rooms:
        raise SystemExit(f"WECHAT_ROOM_NOT_ALLOWED: {args.room}")

    try:
        from wxauto import WeChat
    except ImportError as exc:
        raise SystemExit("wxauto is not installed. Install it in the Windows desktop environment first.") from exc

    wx = WeChat()
    wx.ChatWith(args.room)
    raw_messages = wx.GetAllMessage()[-args.limit :]
    print(json.dumps(raw_messages, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
