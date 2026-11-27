# Project instructions

## Consulting Codex (OpenAI second opinion)

When I ask for an OpenAI review, a Codex review, or a second opinion, consult the Codex CLI:

- Run it read-only from the project root: `codex exec --sandbox read-only "<prompt>"`
  (add `--skip-git-repo-check` if the folder is not a Git repository). Do not grant write
  access unless I explicitly ask for it.
- Make each prompt self-contained. Include the objective, the relevant files, the
  constraints, the specific question to answer, and any conversation context Codex needs.
- Show me Codex's actual response, then assess it yourself: say which recommendations you
  accept or reject, and why. Do not apply its suggestions unreviewed.
- If `codex` is missing or not logged in, tell me instead of skipping the consultation.
