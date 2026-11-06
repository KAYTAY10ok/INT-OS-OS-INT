# Development

Work in the existing checkout. Keep source changes, build outputs and private
configuration separate, following `BUILDING.md`. Use small milestones with an
actual compilation and runtime check before declaring a feature implemented.

`meta-int` owns shared distro settings and the console foundation. Introduce
desktop/security/edition layers only when they contain working integration.
Do not vendor upstream repositories, replace source verification, add foreign
binary feeds, or change the locked architecture during routine maintenance.

For recipe changes run `scripts/int check`, the affected build, and the relevant
guest assertions. For runner changes run `python3 -m unittest discover -s tests`.
Record failed checks and the diagnosis as well as passed checks. Update the
requirement checklist and `CLAUDE_HANDOFF.md` after each verified milestone.
