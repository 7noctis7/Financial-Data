"""CLI du moteur de reporting certifié.

    python3 -m reporting <template> <csv|xlsx|pdf> <AAAA-MM-JJ> [--role R] [--user U]

Exemple :
    python3 -m reporting regulatory pdf 2026-07-09 --role regulatory-officer
"""

import json
import sys

from mesh.audit import AuditLog

from .generator import ReportGenerator, ReportError


def main(argv):
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    template, fmt, date = argv[:3]
    role = argv[argv.index("--role") + 1] if "--role" in argv else "viewer"
    user = argv[argv.index("--user") + 1] if "--user" in argv else "cli-user"
    generator = ReportGenerator(audit_log=AuditLog())
    try:
        metadata = generator.demo(template, fmt, requester=user, role=role,
                                  business_date=date)
    except (ReportError, PermissionError) as exc:
        print(f"REFUSÉ : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
