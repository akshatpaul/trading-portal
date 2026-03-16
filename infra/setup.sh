#!/usr/bin/env bash
# setup.sh — Run ONCE on a fresh Ubuntu 22.04 EC2 instance as root
# Usage: sudo bash setup.sh
# On a fresh Ubuntu 22.04 EC2 instance in ap-south-1
set -euo pipefail

echo "==> Updating package lists..."
apt-get update -q

echo "==> Installing base tools..."
DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common curl git nginx htop unzip

echo "==> Adding deadsnakes PPA for Python 3.12..."
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -q

echo "==> Installing Python 3.12..."
DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12 python3.12-venv

echo "==> Installing Node.js 20 LTS..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs

echo "==> Creating app directory..."
mkdir -p /opt/trading-portal
chown ubuntu:ubuntu /opt/trading-portal

echo "==> Configuring nginx to start on boot..."
systemctl enable nginx

echo "==> Setup complete."
echo "    Next step: run deploy.sh from your local machine:"
echo "    ./infra/deploy.sh <EC2_IP> <PATH_TO_PEM_KEY>"
