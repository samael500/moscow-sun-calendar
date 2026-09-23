"""Contract and integration checks, not a mirror of CSS implementation."""
import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import generate


class StyleIntegrationTests(unittest.TestCase):
    def test_default_is_project_relative(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(generate.resolve_style(), generate.ROOT / 'vendor/brodov-style')
            finally:
                os.chdir(previous)

    def test_invalid_explicit_package_never_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'Invalid brodov-style'):
                generate.resolve_style(root)
            (root / 'package.json').write_text(json.dumps({'name': 'brodov-style', 'interface': 999}))
            with self.assertRaisesRegex(ValueError, 'interface 1'):
                generate.resolve_style(root)
            (root / 'package.json').write_text(json.dumps({'name': 'brodov-style', 'interface': 1}))
            with self.assertRaisesRegex(ValueError, 'missing required file'):
                generate.resolve_style(root)

    def test_override_copies_selected_bytes_preserves_input_and_ics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            explicit = root / 'selected'
            shutil.copytree(generate.resolve_style(), explicit)
            css = explicit / 'css/tokens.css'
            css.write_text(css.read_text() + '\n/* explicit override sentinel */\n')
            before = {p.relative_to(explicit): p.read_bytes() for p in explicit.rglob('*') if p.is_file()}
            city = generate.cities()[0]
            with patch.object(generate, 'cities', return_value=[city]):
                generate.generate_site(root / 'output', date(2026, 9, 23), months=1, history_months=0, style_dir=explicit)
            output = root / 'output'
            self.assertEqual((output / 'brodov-style/css/tokens.css').read_bytes(), css.read_bytes())
            self.assertEqual((output / f"{city['id']}.ics").read_bytes(), generate.build_calendar(date(2026, 9, 23), 1, 0, city).to_ical())
            self.assertEqual(before, {p.relative_to(explicit): p.read_bytes() for p in explicit.rglob('*') if p.is_file()})
            self.assertIn('brodov-style/css/brodov.css', (output / 'index.html').read_text())
            for dangerous in [explicit, explicit / 'output', root]:
                with self.assertRaisesRegex(ValueError, 'must not contain each other'):
                    generate.generate_site(dangerous, style_dir=explicit)

if __name__ == '__main__':
    unittest.main()
