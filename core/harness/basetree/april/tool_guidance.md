# Tool Guidance

- Stdlib-only for system access (`os`, `platform`, `subprocess`); a new pip
  dependency needs a one-line justification in the commit that adds it.
- Preserve the terminal echo of every command run — the user must see what
  executed.
- Keep data local; reach off-box only as an open decision.
- A run's work product lands as deliverable files under `deliverables/`, and the
  run keeps a plain-text `trajectory.txt` alongside them.
