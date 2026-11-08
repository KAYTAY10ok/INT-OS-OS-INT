# Opt-in only after the repository and its public trust anchor are ready.
# No address, public key or signing secret is invented by this include.
PACKAGECONFIG:append:pn-rpm-native = " sequoia"
PACKAGECONFIG:append:pn-rpm = " sequoia"
# Select the intended image explicitly in release configuration. Do not add
# DNF or a repository to installer/unlock initramfs images globally.
