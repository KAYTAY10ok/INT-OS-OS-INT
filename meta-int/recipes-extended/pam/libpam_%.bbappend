# Reject empty passwords in the shared PAM authentication stack. Enrollment
# requires a nonempty password; keep later account changes subject to that rule.
do_install:append:class-target() {
    sed -i -e 's/ nullok_secure//g' -e 's/ nullok//g' \
        ${D}${sysconfdir}/pam.d/common-auth
}
