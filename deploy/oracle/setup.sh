#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/kiwoom-samsung-buy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

mkdir -p "$PROJECT_DIR"
cp "$REPO_DIR/samsung_daily_buy.py" "$PROJECT_DIR/"

if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$PROJECT_DIR/.env"
  chmod 600 "$PROJECT_DIR/.env"
fi

sudo timedatectl set-timezone Asia/Seoul

sudo cp "$SCRIPT_DIR/kiwoom-samsung-buy.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/kiwoom-samsung-buy.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kiwoom-samsung-buy.timer

echo "Installed to $PROJECT_DIR"
echo "Edit secrets: nano $PROJECT_DIR/.env"
echo "Timer status: systemctl list-timers kiwoom-samsung-buy.timer"
echo "Test dry-run: sudo systemctl start kiwoom-samsung-buy.service"
