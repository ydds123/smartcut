# Command Approval Workflow

## Purpose
Reduce repeated approval prompts by standardizing command prefixes and keeping a project-level allowlist.

Important:
- `ops/command_allowlist.yaml` is a governance file for this repository.
- Platform-level prompt suppression still depends on approved `prefix_rule`.

## Files
- `ops/command_allowlist.yaml`: canonical allow/deny prefixes and default policy.
- `ops/command_profiles.yaml`: profile-based subsets (`dev_profile`, `qa_profile`, `ops_profile`).
- `ops/check_command_allowlist.sh`: preflight checker.

## How To Check A Command
```bash
./ops/check_command_allowlist.sh "npm run dev"
./ops/check_command_allowlist.sh npm run dev
```

Possible outputs:
- `ALLOW`: command prefix is approved in repo policy.
- `REVIEW`: command prefix is not listed and needs review.
- `DENY`: command prefix is explicitly blocked.

## Daily Flow
1. Run preflight checker before a new command pattern is used.
2. If `ALLOW`, execute command.
3. If platform asks for approval, approve with persistent `prefix_rule` for that prefix.
4. If `REVIEW`, add prefix to `command_allowlist.yaml` through normal change review.
5. If `DENY`, do not execute unless explicitly approved for a one-off task.

## Change Rules
- Keep `default_policy: deny`.
- Add only stable non-destructive command prefixes.
- Never add destructive patterns (`rm`, `pkill`, `git reset --hard`) to `allow_prefixes`.
- Keep prefixes minimal and specific enough to avoid accidental broad permissions.

## Initial Recommended Prefixes
- `npm run dev`
- `npm run build`
- `npm run lint`
- `python3 -m uvicorn`
- `curl -sS http://localhost:`
- `curl -sS http://127.0.0.1:`
- `lsof -iTCP`
- `ps -ef`
- `tail -n`
