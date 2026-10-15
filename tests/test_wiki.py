from pathlib import Path
import tempfile
import unittest

from scripts.export_wiki import ROOT, PAGES, export, wiki_markdown


class WikiTests(unittest.TestCase):
    def test_export_contains_navigation_and_rewrites_cross_page_links(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            self.assertEqual(export(target, 'example/Kiroshi'), 10)
            self.assertEqual(len(list(target.glob('*.md'))),10)
            self.assertIn('https://github.com/example/Kiroshi/wiki/Installation',(target/'Home.md').read_text())
            self.assertIn('https://github.com/example/Kiroshi/wiki/Traffic-controls',(target/'Dashboard.md').read_text())
            self.assertIn('https://github.com/example/Kiroshi/wiki/Dashboard#claude-code--deepseek-and-codex',(target/'Installation.md').read_text())
            self.assertTrue((target/'_Sidebar.md').exists())
            self.assertTrue((target/'_Footer.md').exists())
            self.assertEqual(len(PAGES),7)

    def test_export_preserves_unmanaged_wiki_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            custom = Path(directory)/'Custom.md'
            custom.write_text('Maintainer-owned page')
            export(directory)
            self.assertEqual(custom.read_text(),'Maintainer-owned page')

    def test_external_links_and_anchors_are_retained(self):
        text='[Site](https://example.test/page) [Section](#tools) [License](../LICENSE)'
        result=wiki_markdown(text,ROOT/'docs/INSTALL.md','example/Kiroshi')
        self.assertIn('[Site](https://example.test/page)',result)
        self.assertIn('[Section](#tools)',result)
        self.assertIn('https://github.com/example/Kiroshi/blob/main/LICENSE',result)

    def test_invalid_destination_and_broken_source_links_are_rejected(self):
        with self.assertRaises(ValueError):
            export(ROOT/'wiki-export')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                export(directory,'invalid/repo/extra')
        with self.assertRaises(ValueError):
            wiki_markdown('[Missing](missing.md)',ROOT/'DASHBOARD.md','example/Kiroshi')


if __name__ == '__main__':
    unittest.main()
