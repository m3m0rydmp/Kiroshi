"""Installation and executable diagnostics; never launches a target scan."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .tools import ROOT, discover
from .config import default_data_dir, database_path


def main():
    parser = argparse.ArgumentParser(description="Check local Kiroshi prerequisites and tool adapters")
    parser.add_argument("--json", action="store_true", help="Print machine-local paths and compatibility as JSON")
    parser.add_argument("--data-dir", default=str(default_data_dir()))
    parser.add_argument("--require-tools", action="store_true", help="Exit nonzero unless every runnable adapter is installed and compatible")
    args = parser.parse_args()
    paths = {}
    database = database_path(Path(args.data_dir).resolve())
    if database.exists():
        try:
            with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
                row = connection.execute("SELECT body FROM records WHERE kind='settings' AND id='local'").fetchone()
                if row:
                    paths = json.loads(row[0]).get("paths", {})
        except (sqlite3.Error, ValueError):
            print("Warning: local overrides could not be read", file=sys.stderr)
    tools = discover(paths, check=True)
    result = dict(python=sys.version.split()[0], repository=str(ROOT), tools=tools,
                  ready=sum(t["runnable"] for t in tools), missing_adapters=[t["name"] for t in tools if t["adapter"] and not t["runnable"]])
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Kiroshi installation doctor — Python {result['python']}")
        print(f"{result['ready']} / {sum(t['adapter'] for t in tools)} scan adapters ready; missing tools do not prevent dashboard startup.\n")
        for tool in tools:
            label = "READY" if tool["runnable"] else "INVENTORY" if tool["installed"] and not tool["adapter"] else "CHECK" if tool["installed"] else "MISSING"
            print(f"{label:9} {tool['name']:20} {tool['path'] or 'not found'}")
            if tool["adapter"] and tool["compatibility"] == "incompatible":
                print(" " * 11 + tool["diagnostic"])
            if tool["override_warning"]:
                print(" " * 11 + tool["override_warning"])
    if args.require_tools and result["missing_adapters"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
