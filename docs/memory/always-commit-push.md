---
name: always-commit-push
description: "Standing preference — finish substantive work by committing AND pushing, without waiting to be asked each time."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8e14b374-5f2b-46d0-88e9-d706b35874e5
---

When work is complete and verified, **commit and push** as the closing step —
do not stop at "want me to commit?" and wait for a go-ahead each time.

**Why:** The user said "always commit and push" directly. This is a standing
preference that overrides the default "commit or push only when the user asks"
rule for this user. It also generalizes the narrower [[session-end-ritual]]
(which only fired at explicit batch/session end) — the user wants the commit+push
to happen at the natural end of any substantive change, not just at session end.

**How to apply:** After finishing and verifying a unit of work (feature, fix,
docs), stage the relevant files, write a descriptive commit (ending with the
Co-Authored-By trailer), and `git push`. Branch first if on the default branch
only when the change warrants it / the user's workflow expects PRs — for this
project the user works directly on `main` and pushes there. Still skip committing
obviously broken / mid-refactor states; "always" means "don't wait to be asked,"
not "commit regardless of quality."
