#!/usr/bin/env bash
# One-time hardening for a fresh Ubuntu Vultr instance.
# Run this as root immediately after the VM is created, before setup-vm.sh:
#
#   ssh root@<vm-ip> 'bash -s' < deploy/harden-vm.sh
#
# It creates a non-root sudo user with your SSH key, disables root/password
# SSH login, and enables a firewall, fail2ban, and automatic security updates.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this as root." >&2
  exit 1
fi

# Create the deploy user and give it passwordless sudo (SSH key is the only
# credential; there's no password to guess).
if ! id "$DEPLOY_USER" &>/dev/null; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG sudo "$DEPLOY_USER"
  echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$DEPLOY_USER"
  chmod 440 "/etc/sudoers.d/90-$DEPLOY_USER"
fi

install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
cp /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"
chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"

# Lock down SSH: no root login, no password auth.
sshd_config=/etc/ssh/sshd_config
sed -i \
  -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
  -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
  -e 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' \
  "$sshd_config"
systemctl restart ssh

# Firewall: allow SSH + HTTP/HTTPS only.
apt-get update -qq
apt-get install -y -qq ufw fail2ban unattended-upgrades
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# fail2ban's default sshd jail is enough for this box.
systemctl enable --now fail2ban

# Unattended security updates.
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now unattended-upgrades

echo "Hardening complete. Log in from now on as: ssh $DEPLOY_USER@<vm-ip>"
