# Trading Portal — AWS Production Deployment

Domain: `alt.akshatpaul.com` · Region: `ap-south-1` (Mumbai) · SSL via Cloudflare

---

## Step 1 — Launch EC2 Instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. **Name:** `trading-portal`
3. **AMI:** Ubuntu 22.04 LTS (64-bit x86)
4. **Instance type:** `t3.small`
5. **Key pair:** Create new → name `trading-key` → download `trading-key.pem`
   ```bash
   chmod 400 trading-key.pem
   ```
6. **Network settings:** Create a new security group with these inbound rules:

   | Type  | Port | Source        | Purpose          |
   |-------|------|---------------|------------------|
   | SSH   | 22   | My IP         | Admin access     |
   | HTTP  | 80   | 0.0.0.0/0     | Cloudflare proxy |
   | HTTPS | 443  | 0.0.0.0/0     | Cloudflare proxy |

7. **Storage:** 20 GiB gp3
8. Click **Launch Instance**

---

## Step 2 — Allocate Elastic IP

1. EC2 → **Elastic IPs** → **Allocate Elastic IP address** → Allocate
2. Select the new IP → **Actions → Associate Elastic IP address**
3. Select your `trading-portal` instance → Associate
4. Note the IP address (e.g. `13.233.x.x`) — you'll use it in every step below

---

## Step 3 — Cloudflare DNS

1. Log in to [Cloudflare](https://dash.cloudflare.com) → select `akshatpaul.com` → **DNS**
2. **Add Record:**
   - Type: `A`
   - Name: `alt`
   - IPv4 address: `<your Elastic IP>`
   - Proxy status: **ON** (orange cloud)
3. Go to **SSL/TLS → Overview** → set mode to **Full**
   - Do NOT use "Full (strict)" — EC2 serves plain HTTP

---

## Step 4 — First-time server setup

Run `setup.sh` on the EC2 instance to install all system packages:

```bash
# Copy setup script to the server
scp -i trading-key.pem infra/setup.sh ubuntu@<EC2_IP>:~/setup.sh

# SSH in and run it as root
ssh -i trading-key.pem ubuntu@<EC2_IP>
sudo bash ~/setup.sh
exit
```

This installs: Python 3.12, Node.js, nginx, git, and creates `/opt/trading-portal`.

---

## Step 5 — Configure .env on server

The `.env` file is **never deployed by rsync** (it's excluded). Set it up manually:

```bash
ssh -i trading-key.pem ubuntu@<EC2_IP>

# Copy the example file
cp /opt/trading-portal/.env.example /opt/trading-portal/.env

# Edit it
nano /opt/trading-portal/.env
```

Key values to set:

```bash
# Generate a bcrypt hash for your password:
python3.12 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
# Paste the output as TRADING_PASSWORD_HASH

# Generate a random JWT secret:
python3.12 -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as JWT_SECRET
```

Fill in your Zerodha API keys, Telegram credentials, and any other required values.

---

## Step 6 — Deploy

Run from your **local machine** (not the server):

```bash
./infra/deploy.sh <EC2_IP> ~/.ssh/trading-key.pem
```

This will:
1. Build the React frontend (`npm run build`)
2. Rsync all code to `/opt/trading-portal/` on EC2 (excluding `.env`, `venv`, `node_modules`)
3. Install Python dependencies into `/opt/trading-portal/venv/`
4. Install and restart the `trading-backend` systemd service
5. Configure and reload nginx

---

## Step 7 — Verify

```bash
# Health check (bypasses auth)
curl http://<EC2_IP>/health
# Expected: {"status":"ok"}

# Via Cloudflare domain
curl https://alt.akshatpaul.com/health
# Expected: {"status":"ok"}
```

Open `https://alt.akshatpaul.com` in your browser — you should see the login page.

---

## Ongoing Deploys

After any code change, simply run:

```bash
./infra/deploy.sh <EC2_IP> ~/.ssh/trading-key.pem
```

No server SSH needed unless you're changing `.env` values.

---

## Troubleshooting

```bash
# Check backend service status
ssh -i trading-key.pem ubuntu@<EC2_IP>
sudo systemctl status trading-backend

# View live backend logs
sudo journalctl -u trading-backend -f

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Test nginx config
sudo nginx -t

# Restart services manually
sudo systemctl restart trading-backend
sudo systemctl reload nginx
```

---

## Architecture

```
Browser → Cloudflare (SSL termination) → EC2:80 (nginx)
                                              ├── /          → /opt/trading-portal/frontend/dist (React)
                                              ├── /api/      → localhost:8000 (FastAPI/uvicorn)
                                              ├── /health    → localhost:8000 (unauthenticated)
                                              └── /ws        → localhost:8000 (WebSocket)
```
