#!/usr/bin/env python3
"""Export versioned Markdown guides into a local GitHub Wiki checkout; no network writes."""
import argparse
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = {
    'docs/INSTALL.md': 'Installation',
    'DASHBOARD.md': 'Dashboard',
    'docs/TRAFFIC.md': 'Traffic-controls',
    'docs/NOTIFICATIONS.md': 'Notifications',
    'docs/PERFORMANCE.md': 'Performance',
    'docs/LOGIC_REVIEW.md': 'Business-logic-review',
    'docs/SCAFFOLD.md': 'Scaffold-CLI',
}


def wiki_markdown(text, source, repository):
    base = f'https://github.com/{repository}'
    def link(match):
        target = match.group(2).strip()
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path or target.startswith('/'):
            return match.group(0)
        path = (source.parent / parsed.path).resolve()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            raise ValueError(f'Link outside repository: {target}') from None
        if relative in PAGES:
            destination = base + '/wiki/' + PAGES[relative]
        else:
            if not path.exists():
                raise ValueError(f'Broken documentation link in {source.name}: {target}')
            destination = base + '/blob/main/' + relative
        if parsed.fragment:
            destination += '#' + parsed.fragment
        return f'{match.group(1)}({destination})'
    return re.sub(r'(\[[^\]\n]*\])\(([^)\n]+)\)', link, text)


def export(output, repository='m3m0rydmp/Kiroshi'):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Use an owner/repository name')
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('Export to a separate Wiki checkout outside the project repository')
    output.mkdir(parents=True, exist_ok=True)
    base = f'https://github.com/{repository}'
    for source, title in PAGES.items():
        path = ROOT / source
        text = wiki_markdown(path.read_text(), path, repository)
        text += f'\n---\n[Versioned source]({base}/blob/main/{source}) · [Project]({base})\n'
        (output / (title + '.md')).write_text(text)
    navigation = '\n'.join(f'- [{title.replace("-", " ")}]({base}/wiki/{title})' for title in PAGES.values())
    home = f'''# Kiroshi documentation

Kiroshi is a local Linux/WSL dashboard for authorized bug bounty engagements. It
runs your installed tools, organizes recon data and optionally analyzes collected
evidence with Claude / your configured provider or Codex. Docker is not required.

## Start here

1. [Install Kiroshi and detect your tools]({base}/wiki/Installation).
2. [Create an engagement, preview a workflow and follow live execution]({base}/wiki/Dashboard).
3. Search and filter the asset cache; add exact-origin sessions when needed.
4. Prepare a selected engagement's context in **Agent handoff**, review it and
   explicitly start analysis with your chosen provider.

New workflows default to unlimited total jobs and targets per stage. Scope, rate,
individual tool timeouts and traffic holds still apply. AI is optional; scanner
completion is not proof of a vulnerability. Existing workflows retain saved limits.

## Guides

{navigation}

## Source and credits

These pages are generated from the [versioned documentation]({base}/tree/main/docs).
For changes, edit the repository guides and follow [Wiki publishing]({base}/blob/main/docs/WIKI.md).

Kiroshi retains the MIT-licensed scaffold and methodology from
[0xcucumbersalad/hunt](https://github.com/0xcucumbersalad/hunt).
'''
    (output / 'Home.md').write_text(home)
    (output / '_Sidebar.md').write_text(f'[Documentation home]({base}/wiki)\n\n' + navigation + f'\n\n[Source repository]({base})\n')
    (output / '_Footer.md').write_text(f'[Kiroshi]({base}) · Local Linux/WSL dashboard · [MIT license]({base}/blob/main/LICENSE)\n')
    return len(PAGES) + 3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Separate local Wiki checkout to populate')
    parser.add_argument('--repository', default='m3m0rydmp/Kiroshi')
    args = parser.parse_args()
    print(f'Exported {export(args.output, args.repository)} Wiki files to {args.output.resolve()}')
