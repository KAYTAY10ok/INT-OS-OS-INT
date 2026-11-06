# Keep upstream's required runtime dependencies. Select optional applications in
# the INT package group instead of implicitly installing every Sway extra.
# Set this in recipe context so expansion of ${PN} cannot replace a conf key.
RRECOMMENDS:${PN} = ""
