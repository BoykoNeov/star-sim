---
name: star-sim-github-repo
description: "Star Simulator is a public GitHub repo at BoykoNeov/star-sim — location, default branch, push protocol"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8d890850-1473-43b3-adb1-c7ca0e98ecf7
---

Star Simulator's public GitHub repo: **https://github.com/BoykoNeov/star-sim**
(owner `BoykoNeov`, default branch `main`, visibility PUBLIC). Created
2026-06-20 with `gh repo create star-sim --public --source=. --remote=origin
--push`. Remote `origin` uses SSH (`git@github.com:BoykoNeov/star-sim.git`).

Local clone: `M:\claud_projects\star-sim`. The `data/` grids (~180 MB tarball +
~1.2 GB extracted) are gitignored and NOT in the repo — they're fetched at build
time via `python -m star_sim.fetch_mist`. Largest tracked blob is ~16 KB; keep
it that way (no data, no binaries).

Pushing is the closing step of the [[session-end-ritual]]. Note the project's
`.claude/settings.json` has a default `deny` on `git push` as a safety rail; the
user's standing session-end instruction is the authorization that overrides it.
See [[star-sim-mist-provider]] for what's in the repo.
