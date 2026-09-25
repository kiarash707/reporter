# systemd deployment

```bash
# 1. install into /opt/reporter with a dedicated user (recommended for servers)
sudo install -d -o "$USER" -g "$USER" /opt/reporter
git clone <your-repo-url> /opt/reporter
cd /opt/reporter

# 2. one command: venv + dependencies + .env + unit + service
sudo bash scripts/install.sh --service --dir /opt/reporter --user "$USER"

# 3. fill in the credentials, then start
sudo nano /opt/reporter/.env
sudo systemctl restart reporter
```

Useful commands:

```bash
systemctl status reporter          # current state
journalctl -u reporter -f          # live logs
journalctl -u reporter -p err -n 50  # only errors
sudo systemctl restart reporter    # after a config change
```

The generated unit is derived from `reporter.service.in`. Re-run the installer
(or re-render the template) whenever the install path or user changes.
