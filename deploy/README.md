# Deploying the app

## Local (native, for trying it out)

```bash
deploy/local-deploy.sh start   # sets up venv/npm deps, launches both servers
deploy/local-deploy.sh status  # check if it's up
deploy/local-deploy.sh stop
```

Runs the backend with `uvicorn` and the frontend with the Vite dev server
directly on the host (no Docker) — useful when you already have a real Lean
toolchain set up locally and just want to click around the UI. Both bind to
`0.0.0.0`, so if you're on Tailscale, `local-deploy.sh start` also prints a
Tailscale URL for reaching it from another device (e.g. your phone).

## Vultr (mock-mode, for hosting)

This deploys the frontend + backend in mock mode (`ALLOW_MOCK_FALLBACK=true`,
no real Lean/Mathlib toolchain). Verification calls fall back to the mock
validator; theorem formalization still uses the Gemini API.

## Quick path: one command

Install [`vultr-cli`](https://github.com/vultr/vultr-cli) and point it at
your API key (`~/.vultr-cli.yaml` with `api-key: ...`, or the `VULTR_API_KEY`
env var), then:

```bash
deploy/deploy.sh
```

This creates the VM, hardens it, installs Docker, clones the repo, and
brings the app up over HTTPS — no other manual steps. It also picks up your
Gemini API key automatically if it can find one, checked in this order:

1. `$GEMINI_API_KEY` env var
2. `$GEMINI_API_KEY_FILE` env var (path to a file containing just the key)
3. `~/.config/lean-autoformalizer/gemini-api-key` (default file location)

If none of those are set, the app still comes up (mock mode still works),
but formalization calls will fail until you SSH in and set
`GEMINI_API_KEY` in `backend/.env` yourself — `deploy.sh` prints the exact
commands to do that when it can't find a key.

Tear down with `deploy/vultr-vm.sh destroy` (see step 6 below).

## Manual path (step by step)

Useful if you want more control, or to debug a step in isolation.
`deploy/deploy.sh` is just these steps chained together over SSH.

### 1. Create the VM

With `vultr-cli` installed and configured (see Quick path above):

```bash
deploy/vultr-vm.sh create
```

This provisions a $5/mo `vc2-1c-1gb` instance (1 vCPU, 1GB RAM, 25GB SSD) in
`ewr` (New Jersey) running Ubuntu 24.04 LTS, uploading/reusing an SSH key
named `<hostname>-lean-autoformalizer` from `~/.ssh/id_ed25519.pub`. It
prints the VM's IP and records the instance ID in `deploy/.vultr-instance-id`
(not committed) so `destroy` can find it later.

### 2. Harden the VM

```bash
ssh root@<vm-ip> 'bash -s' < deploy/harden-vm.sh
```

This creates a non-root `deploy` user (with your SSH key and passwordless
sudo), disables root SSH login and password authentication, and enables
`ufw` (allowing only SSH/80/443), `fail2ban`, and unattended security
updates. From this point on, log in as `deploy@<vm-ip>`, not `root`.

### 3. Run the setup script

```bash
ssh deploy@<vm-ip>
curl -fsSL https://raw.githubusercontent.com/javadnoorb/lean-autoformalizer/main/deploy/setup-vm.sh -o setup-vm.sh
bash setup-vm.sh
```

The first run installs Docker and adds you to the `docker` group — log out
and back in, then rerun. The next run clones the repo and creates
`backend/.env` from the example file, then stops so you can fill in your API
key:

```bash
nano ~/lean-autoformalizer/backend/.env
```

Set `GEMINI_API_KEY` to your key. Leave `ALLOW_MOCK_FALLBACK=true`. Then run
`bash setup-vm.sh` again to build and start the containers.

The script also generates `Caddyfile` from `Caddyfile.template`, filling in
an [sslip.io](https://sslip.io) hostname derived from the VM's current
public IP (e.g. `45-76-166-10.sslip.io`) — this gives every fresh VM a real,
resolvable HTTPS domain with zero manual DNS setup, and it self-adjusts if
the VM gets a different IP after a destroy/recreate cycle. Caddy uses this
to automatically obtain and renew a Let's Encrypt certificate.

### 4. Verify it's up

Visit `https://<the-sslip.io-domain-printed-by-setup-vm.sh>` in your
browser — you should see the app over HTTPS, with plain HTTP redirecting to
it. Caddy terminates TLS and proxies to the frontend (nginx), which serves
the static build and proxies `/api/*` requests to the backend container.

If you have your own domain instead of using sslip.io, point its A record
at the VM's IP and edit `Caddyfile.template`'s `{{DOMAIN}}` placeholder to
your domain before running `setup-vm.sh`.

Check container status/logs from the VM if something looks wrong:

```bash
cd ~/lean-autoformalizer
docker compose ps
docker compose logs -f
```

### 5. Updating after a code change

```bash
cd ~/lean-autoformalizer
git pull
docker compose up -d --build
```

### 6. Tearing down to save cost

Since mock mode has no Mathlib cache to lose, there's nothing worth
snapshotting:

```bash
deploy/vultr-vm.sh destroy
```

Re-run steps 1-3 next time you need it up; the whole cycle (VM boot,
hardening, app build) takes a few minutes.

If you'd rather not repeat the Gemini API key step each time, take a
**snapshot** after step 3 completes once; deploying from that snapshot next
time skips straight to a running app (you'll get a new IP, and Vultr charges
a small ongoing fee for snapshot storage while the instance is destroyed).

## Mathlib import benchmark (throwaway VM, unrelated to the app deploy above)

```bash
deploy/mathlib-bench.sh run          # create a VM, time `import Mathlib`, auto-destroy when done
deploy/mathlib-bench.sh run --keep   # same, but leave the VM up afterward to poke around
deploy/mathlib-bench.sh ssh          # SSH into a --keep'd VM
deploy/mathlib-bench.sh destroy      # tear down a --keep'd VM (or clean up after a failed run)
```

`run` tears the VM down automatically on exit -- success, failure, or
Ctrl-C -- unless `--keep` is passed, since the real cost risk here is
forgetting to destroy a billed instance, not destroying one too eagerly.
Since the VM (and its own copy of the results) disappears at the end,
`run` `tee`s everything the remote script prints to a local, timestamped
file under `deploy/mathlib-bench-results/` (gitignored) as it streams
back over SSH -- that's the durable record, not anything left on the VM.

Answers "is Mathlib-import slowness a resource ceiling on this dev machine,
or inherent to the tool/approach?" (see
`.claude/skills/lean-interactive-search/SKILL.md` for the investigation
that raised the question -- locally, a bare `import Mathlib` took 1h08m and
thrashed on a 6GB-RAM box holding a 6GB Mathlib build). Provisions a
separate, separately-tracked `vhf-3c-8gb` instance (8GB RAM, high-frequency
CPU, ~$48/mo i.e. a few cents for a one-off run) via the same `vultr-vm.sh`
create/destroy this deploy uses, but under a different label/state file so
it can never collide with the tracked app instance. Deliberately skips
`harden-vm.sh` -- this box only lives for the length of the test and is
destroyed right after, so the security hardening buys nothing here. On the
VM it installs `elan`, clones `mathlib4` at latest master, runs
`lake exe cache get` to pull prebuilt `.olean`s (falling back to a
from-source `lake build Mathlib` only if the cache doesn't cover that
commit), then times `lake env lean` on a file containing just
`import Mathlib` via `/usr/bin/time -v`.

**Result (see `.claude/skills/lean-interactive-search/SKILL.md` for the
full context): confirmed it's the RAM, not the tools.** Cache fetch 68s,
`import Mathlib` itself 21.58s wall clock, peak RSS 6.1GB, 40,946 major
page faults -- versus 1h08m and 599,255 major page faults on the local
6GB-capped box for the identical import. ~190x faster from 2GB of extra
headroom alone.

The create/wait-for-ssh/log/auto-destroy machinery both this script and
`pantograph-bench.sh` (below) share lives in `cloud-bench-lib.sh`, sourced
by each -- if you're adding a third one-off cloud benchmark, add a new
`<name>-bench.sh` + `<name>-bench-remote.sh` pair following the same
pattern rather than writing the orchestration again.

## PyPantograph Mathlib benchmark (same idea, for the actual interactive-search tool)

```bash
deploy/pantograph-bench.sh run          # create a VM, time Server(imports=['Mathlib']), auto-destroy
deploy/pantograph-bench.sh run --keep   # same, but leave the VM up afterward
deploy/pantograph-bench.sh ssh          # SSH into a --keep'd VM
deploy/pantograph-bench.sh destroy      # tear down a --keep'd VM
```

Same throwaway-VM pattern as `mathlib-bench.sh`, but for the thing that
actually matters for interactive search: locally, PyPantograph's
`Server(imports=['Mathlib'], ...)` hung 35+ minutes on the 6GB-RAM box
without ever reaching "ready" (see the SKILL.md section on PyPantograph).
On the VM, it sets up a minimal project pinned to Mathlib `v4.33.1` (the
exact version the local PyPantograph submodule fix was matched against),
builds PyPantograph from that same fixed source, then times
`Server(imports=['Mathlib'])` followed by a `goal_start`/`goal_tactic`
call, the same measurement taken locally.

**Result: 33.2s to start a session (vs. 35+ min hung locally), then 17ms
per `goal_tactic` call with a correct `is_solved`.** Full writeup in
`.claude/skills/lean-interactive-search/SKILL.md`.

## Interactive session API benchmark (exercises the real app, not just the library)

```bash
deploy/pantograph-service-bench.sh run          # create a VM, deploy this app, curl the real endpoints, auto-destroy
deploy/pantograph-service-bench.sh run --keep   # same, but leave the VM up afterward
deploy/pantograph-service-bench.sh ssh          # SSH into a --keep'd VM
deploy/pantograph-service-bench.sh destroy      # tear down a --keep'd VM
```

One level up from `pantograph-bench.sh`: instead of a standalone Python
script calling PyPantograph directly, this sets up the same version-matched
PyPantograph install, then clones this repo (`BENCH_REF` env var, default
the current local branch), installs `backend/requirements.txt` into the
same venv, launches the real `uvicorn app.main:app`, and drives the actual
`/api/interactive/*` endpoints (`backend/app/services/pantograph_sessions.py`)
with `curl` -- start a session, apply tactics, confirm `is_solved`, close
it, and check the `INTERACTIVE_MAX_SESSIONS` 429 and unknown-session 404
paths for real. This is the only way to verify that service end-to-end,
since it needs the same properly-sized hardware the library itself does.
