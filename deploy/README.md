# Deploying the mock-mode app to Vultr

This deploys the frontend + backend in mock mode (`ALLOW_MOCK_FALLBACK=true`,
no real Lean/Mathlib toolchain). Verification calls fall back to the mock
validator; theorem formalization still uses the Gemini API.

## 1. Create the VM

In the Vultr dashboard, deploy a new Cloud Compute instance:

- **Image**: Ubuntu 24.04 LTS
- **Plan**: Regular Performance, $5/mo (1 vCPU, 1GB RAM, 25GB SSD) — plenty for mock mode
- Add your SSH key during creation so you can log in without a password

Once it's running, note its IP address and SSH in:

```bash
ssh root@<vm-ip>
```

## 2. Run the setup script

On the VM:

```bash
curl -fsSL https://raw.githubusercontent.com/javadnoorb/lean-autoformalizer/main/deploy/setup-vm.sh -o setup-vm.sh
bash setup-vm.sh
```

The first run installs Docker, clones the repo, creates `backend/.env` from
the example file, and then stops so you can fill in your API key:

```bash
nano ~/lean-autoformalizer/backend/.env
```

Set `GEMINI_API_KEY` to your key. Leave `ALLOW_MOCK_FALLBACK=true`.

Then run the script again to build and start the containers:

```bash
bash setup-vm.sh
```

## 3. Verify it's up

Visit `http://<vm-ip>` in your browser — you should see the app. The
frontend (nginx) serves the static build on port 80 and proxies `/api/*`
requests to the backend container.

Check container status/logs from the VM if something looks wrong:

```bash
cd ~/lean-autoformalizer
sudo docker compose ps
sudo docker compose logs -f
```

## 4. Updating after a code change

```bash
cd ~/lean-autoformalizer
git pull
sudo docker compose up -d --build
```

## 5. Tearing down to save cost

Since mock mode has no Mathlib cache to lose, there's nothing worth
snapshotting — just destroy the instance from the Vultr dashboard when
you're done, and re-run steps 1-2 next time. The whole setup (VM boot +
script) takes a few minutes.

If you'd rather not repeat the API key step each time, take a **snapshot**
after step 2 completes once; deploying from that snapshot next time skips
straight to a running app (you'll get a new IP, and Vultr charges a small
ongoing fee for snapshot storage while the instance is destroyed).
