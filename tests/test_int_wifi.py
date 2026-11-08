"""Host tests for int-wifi with fake iw/wpa_passphrase/systemctl on a pty."""
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "meta-int/recipes-connectivity/int-wifi/files/int-wifi"

FAKES = {
    "iw": '#!/bin/sh\necho "iw $*" >> "$LOG"\n'
          'if [ "$3" = scan ]; then printf "BSS aa(on wlan0)\\n\\tsignal: -45.00 dBm\\n\\tSSID: Maison\\n'
          'BSS bb(on wlan0)\\n\\tsignal: -80.00 dBm\\n\\tSSID: Voisin\\n"; fi\n',
    "wpa_passphrase": '#!/bin/sh\necho "wpa_passphrase $*" >> "$LOG"\nread -r p\n'
                      'printf "network={\\n\\tssid=\\"%s\\"\\n\\t#psk=\\"%s\\"\\n\\tpsk=0123abcd\\n}\\n" "$1" "$p"\n',
    "systemctl": '#!/bin/sh\necho "systemctl $*" >> "$LOG"\n',
    "ip": '#!/bin/sh\necho "ip $*" >> "$LOG"\n',
    "sudo": '#!/bin/sh\nshift\nexec "$@"\n',
}


class WifiTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, body in FAKES.items():
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        (self.root / "net/wlan0/wireless").mkdir(parents=True)
        (self.root / "net/eth0").mkdir(parents=True)
        self.log = self.root / "log"
        self.log.write_text("")
        self.conf = self.root / "conf"
        self.env = {"INT_WIFI_PATH": "%s:/usr/bin:/bin" % bin_dir, "INT_WIFI_SYS_NET": str(self.root / "net"),
                    "INT_WIFI_CONF_DIR": str(self.conf), "LOG": str(self.log), "LANG": "C", "HOME": str(self.root)}

    def run_tty(self, args, typed=""):
        """Run int-wifi with a pty as stdin (it reads the password from a terminal)."""
        master, slave = pty.openpty()
        proc = subprocess.Popen(["/bin/sh", str(SCRIPT), *args], stdin=slave, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=self.env, text=True)
        os.close(slave)
        time.sleep(0.5)
        if typed:
            os.write(master, typed.encode())
        out, err = proc.communicate(timeout=20)
        os.close(master)
        return proc.returncode, out, err

    def test_scan_lists_networks_by_signal(self):
        result = subprocess.run(["/bin/sh", str(SCRIPT), "scan"], env=self.env, capture_output=True, text=True,
                                timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertTrue(lines[0].endswith("Maison"), lines)
        self.assertTrue(lines[1].endswith("Voisin"), lines)

    def test_connect_stores_only_the_hash_and_never_argv(self):
        code, out, err = self.run_tty(["connect", "Maison"], "motdepasse123\n")
        self.assertEqual(code, 0, err)
        conf = (self.conf / "wpa_supplicant-wlan0.conf").read_text()
        self.assertIn("psk=0123abcd", conf)
        self.assertNotIn("motdepasse123", conf)
        self.assertEqual(oct((self.conf / "wpa_supplicant-wlan0.conf").stat().st_mode & 0o777), "0o600")
        log = self.log.read_text()
        self.assertNotIn("motdepasse123", log)  # not in any argv
        self.assertIn("wpa_passphrase Maison", log)
        self.assertIn("systemctl restart wpa_supplicant@wlan0.service", log)

    def test_bad_input_is_refused(self):
        self.assertEqual(self.run_tty(["connect", "Maison"], "court\n")[0], 2)
        self.assertEqual(self.run_tty(["connect", 'a"b'], "")[0], 2)
        self.assertEqual(self.run_tty(["connect", "a\nnetwork={"], "")[0], 2)
        self.assertEqual(self.run_tty(["connect", "x" * 33], "")[0], 2)
        self.assertFalse((self.conf / "wpa_supplicant-wlan0.conf").exists())

    def test_no_wifi_card(self):
        (self.root / "net/wlan0/wireless").rmdir()
        result = subprocess.run(["/bin/sh", str(SCRIPT), "status"], env=self.env, capture_output=True, text=True,
                                timeout=20)
        self.assertEqual(result.returncode, 4)
        self.assertIn("No Wi-Fi card", result.stderr)

    def test_network_file_uses_dhcp_for_wlan(self):
        net = (SCRIPT.parent / "25-int-wireless.network").read_text()
        self.assertIn("Type=wlan", net)
        self.assertIn("DHCP=yes", net)


if __name__ == "__main__":
    unittest.main()
