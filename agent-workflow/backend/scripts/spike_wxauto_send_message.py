from __future__ import annotations

import argparse
import os


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike: send a feedback message to a whitelisted WeChat group via wxauto.")
    parser.add_argument("--room", required=True, help="Exact whitelisted group name.")
    parser.add_argument("--text", required=True, help="Message text to send.")
    args = parser.parse_args()

    if os.getenv("AGENT_WORKFLOW_WECHAT_SEND_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise SystemExit("WECHAT_SEND_DISABLED")

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
    wx.SendMsg(args.text, who=args.room)
    print("sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
