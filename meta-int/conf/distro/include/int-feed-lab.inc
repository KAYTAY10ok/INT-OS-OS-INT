# Isolated development profile: build real RPM OpenPGP support. These flags do
# not sign or publish anything and do not provide release key custody.
PACKAGECONFIG:append:pn-rpm-native = " sequoia"
PACKAGECONFIG:append:pn-rpm = " sequoia"
