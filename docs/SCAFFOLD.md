# Original scaffold CLI

The retained `hunt` Bash script creates a target folder and an `AGENT.md` reference
brief. The dashboard invokes it for each engagement, then supplies shared instructions
and evidence-readiness guidance that take precedence over the reference brief.

```bash
./hunt "Acme Corp"
./hunt acme --force
./hunt acme < /dev/null
```

An interactive terminal prompts for program policy, in-scope and excluded assets.
Non-interactive runs leave placeholders. The scaffold itself makes no target requests.
`--force` overwrites an existing brief; review it before using that option.

The script and original methodology are by
[0xcucumbersalad](https://github.com/0xcucumbersalad), from
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt), under the retained
MIT license. See the original repository for its history and upstream documentation.

To install only the scaffold CLI, independently of the dashboard:

```bash
mkdir -p "$HOME/.local/bin"
install -m 0755 hunt "$HOME/.local/bin/hunt"
```

Keep local credentials and evidence outside tracked files. The dashboard's
`QUALITY.md` and bounded scope/traffic settings should be used for agent work.
