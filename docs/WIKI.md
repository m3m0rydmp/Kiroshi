# Publishing the GitHub Wiki

The README provides an overview and quick start. Detailed user guides are published
in the [GitHub Wiki](https://github.com/m3m0rydmp/Kiroshi/wiki), with their versioned
source retained in this repository. Edit the source guides rather than making
independent edits in both locations. Wiki updates are separate Git commits and pushes.

## First publication

GitHub requires an initial page before the Wiki Git repository can be cloned.
The repository owner opens **Wiki → Create the first page**, saves a Home page,
then clones the Wiki. See [GitHub's Wiki instructions](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages).

```bash
git clone https://github.com/m3m0rydmp/Kiroshi.wiki.git "$HOME/Kiroshi.wiki"
```

## Export and publish

From the Kiroshi source checkout, after updating its Markdown guides:

```bash
python3 scripts/export_wiki.py --output "$HOME/Kiroshi.wiki"
git -C "$HOME/Kiroshi.wiki" diff --check
git -C "$HOME/Kiroshi.wiki" diff
```

The exporter writes seven guides, Home, a sidebar and a footer. Relative links are
rewritten for Wiki navigation; links to repository files point to `main`. Other
Wiki files are preserved, but managed pages are overwritten from their versioned
sources. Review and bring any independent edits back into the source first.

After reviewing the concrete export, commit the listed Markdown files and push the
Wiki's existing default branch. The exporter itself makes no network requests and
does not commit or publish. For a fork, pass `--repository OWNER/REPOSITORY`.
