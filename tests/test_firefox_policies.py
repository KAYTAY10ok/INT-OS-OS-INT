"""The OS-INT Firefox policies stay hardened and the browser image stays isolated."""
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
RECIPE = REPO/'meta-int/recipes-browser/int-firefox-policies'
IMAGE = REPO/'meta-int/dynamic-layers/firefox-browser-layer/recipes-core/images/int-image-osint-browser.bb'


class FirefoxPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policies = json.loads((RECIPE/'files/policies.json').read_text())['policies']

    def test_telemetry_studies_and_vendor_messaging_are_off(self):
        for name in ('DisableTelemetry', 'DisableFirefoxStudies', 'DisableAppUpdate'):
            self.assertIs(self.policies[name], True, name)
        self.assertIs(self.policies['GenerativeAI']['Enabled'], False)
        self.assertIs(self.policies['UserMessaging']['ExtensionRecommendations'], False)

    def test_doh_is_off_by_default_but_user_may_enable_it(self):
        self.assertEqual({'Enabled': False, 'Locked': False}, self.policies['DNSOverHTTPS'])

    def test_tracking_protection_is_strict(self):
        protection = self.policies['EnableTrackingProtection']
        self.assertEqual((True, 'strict'), (protection['Value'], protection['Category']))

    def test_no_password_saving_prompt_by_default(self):
        self.assertIs(self.policies['OfferToSaveLoginsDefault'], False)
        self.assertNotIn('PasswordManagerEnabled', self.policies)

    def test_no_extension_is_downloaded_automatically(self):
        text = (RECIPE/'files/policies.json').read_text()
        self.assertNotIn('install_url', text)
        self.assertNotIn('force_installed', text)
        self.assertNotIn('normal_installed', text)
        self.assertNotIn('addons.mozilla.org', text)
        self.assertEqual({'installation_mode': 'allowed'},
                         self.policies['ExtensionSettings']['uBlock0@raymondhill.net'])

    def test_recipe_installs_system_policy_path(self):
        recipe = (RECIPE/'int-firefox-policies_1.0.bb').read_text()
        self.assertIn('${sysconfdir}/firefox/policies/policies.json', recipe)
        self.assertNotIn('RDEPENDS', recipe)

    def test_browser_image_extends_live_without_modifying_it(self):
        image = IMAGE.read_text()
        self.assertIn('\nrequire ../../../int-desktop/recipes-core/images/int-image-live.bb\n', image)
        live = IMAGE.parent / '../../../int-desktop/recipes-core/images/int-image-live.bb'
        self.assertTrue(live.resolve().is_file())
        for package in ('firefox', 'int-firefox-policies'):
            self.assertRegex(image, rf'(?m)^\s+{package}\s*\\$')
        self.assertNotIn('firefox', live.read_text())
        layer = (REPO/'meta-int/conf/layer.conf').read_text()
        self.assertIn('BBFILES_DYNAMIC += "firefox-browser-layer:${LAYERDIR}/dynamic-layers/'
                      'firefox-browser-layer/recipes-*/*/*.bb"', layer)

    def test_live_image_is_parsed_only_with_the_desktop_layer(self):
        # meta-int alone (core/feed profiles) must not contain a recipe that
        # requires an image from meta-int-desktop.
        self.assertFalse((REPO/'meta-int/recipes-core/images/int-image-live.bb').exists())
        layer = (REPO/'meta-int/conf/layer.conf').read_text()
        self.assertIn('BBFILES_DYNAMIC += "int-desktop:${LAYERDIR}/dynamic-layers/int-desktop/recipes-*/*/*.bb"', layer)
        for recipe in (REPO/'meta-int').glob('recipes-*/*/*.bb'):
            self.assertNotIn('int-image-desktop.bb', recipe.read_text(), recipe)


if __name__ == '__main__':
    unittest.main()
