"""Admin CLI for trial invite codes (same ``AIE_WEB_*`` environment as the server).

Run from the repository root with ``apps/web`` on ``sys.path``::

    python -m aie_web.admin issue [--hours 72] [--max-projects 5] [--label NAME] [--count 1]
    python -m aie_web.admin list
    python -m aie_web.admin revoke CODE_OR_ID     # also deletes the code's projects now
    python -m aie_web.admin sweep                 # delete projects of expired/revoked codes now

A raw code is printed only once, when it is issued; only its hash is stored.
"""

import argparse
import sys
import time
from collections.abc import Sequence

from .store import ProjectStore, Settings
from .trial import InviteStore


def _remaining(seconds: float) -> str:
    if seconds <= 0:
        return "0h"
    hours, rest = divmod(int(seconds), 3600)
    return f"{hours}h{rest // 60:02d}m"


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    config = settings or Settings.from_env()
    parser = argparse.ArgumentParser(prog="python -m aie_web.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    issue = sub.add_parser("issue", help="issue new invite code(s)")
    issue.add_argument("--hours", type=float, default=config.trial_code_hours)
    issue.add_argument("--max-projects", type=int, default=config.trial_max_projects)
    issue.add_argument("--label", default="")
    issue.add_argument("--count", type=int, default=1)
    sub.add_parser("list", help="list codes with status, remaining time and usage")
    revoke = sub.add_parser("revoke", help="revoke a code and delete its projects now")
    revoke.add_argument("code")
    sub.add_parser("sweep", help="delete projects of expired or revoked codes now")
    args = parser.parse_args(list(argv) if argv is not None else None)

    invites = InviteStore(config.invites_path)
    store = ProjectStore(config)
    now = time.time()
    if args.command == "issue":
        for _ in range(max(1, args.count)):
            code, invite = invites.issue(args.hours, args.max_projects, args.label)
            print(
                f"{code}  id={invite.code_id}  valid {invite.valid_hours:g}h from first use, "
                f"max {invite.max_projects} projects"
            )
        return 0
    if args.command == "list":
        print("id            status   label                used/max  remaining  first use")
        for invite in invites.list():
            expires = invite.expires_at
            remaining = (
                f"{invite.valid_hours:g}h (unused)"
                if expires is None
                else _remaining(expires - now)
            )
            first = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(invite.first_used_at))
                if invite.first_used_at
                else "-"
            )
            print(
                f"{invite.code_id:<13} {invite.status(now):<8} {invite.label[:20]:<20} "
                f"{invite.projects_created}/{invite.max_projects:<6} {remaining:<10} {first}"
            )
        return 0
    if args.command == "revoke":
        revoked = invites.revoke(args.code)
        if revoked is None:
            print("no such code", file=sys.stderr)
            return 1
        removed = store.delete_for_codes({revoked.code_id})
        print(f"revoked {revoked.code_id}; deleted {removed} project(s)")
        return 0
    removed = store.delete_for_codes(invites.dead_code_ids(now))
    print(f"deleted {removed} project(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
