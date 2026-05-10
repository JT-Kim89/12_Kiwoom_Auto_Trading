from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


KST = timezone(timedelta(hours=9), "KST")
LIVE_CONFIRM_PHRASE = "BUY_SAMSUNG_005930_DAILY"


@dataclass(frozen=True)
class Config:
    app_key: str
    secret_key: str
    env: str
    dry_run: bool
    confirm_live_order: str
    stock_code: str
    quantity: str
    exchange: str
    trade_type: str
    order_price: str
    condition_price: str
    order_time: dt_time
    max_lateness_minutes: int
    holidays: set[str]
    log_path: Path
    state_path: Path

    @property
    def base_url(self) -> str:
        if self.env == "real":
            return "https://api.kiwoom.com"
        if self.env == "mock":
            return "https://mockapi.kiwoom.com"
        raise ValueError("KIWOOM_ENV must be 'mock' or 'real'.")


class KiwoomRestClient:
    def __init__(self, config: Config):
        self.config = config
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    def issue_token(self) -> str:
        now = datetime.now(KST)
        if self._token and self._token_expires_at and now < self._token_expires_at - timedelta(minutes=5):
            return self._token

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.app_key,
            "secretkey": self.config.secret_key,
        }
        data = self._post_json("/oauth2/token", payload, headers={})
        token = data.get("token")
        if not token:
            raise RuntimeError(f"Token response did not include token: {data}")

        expires_dt = data.get("expires_dt")
        if isinstance(expires_dt, str) and len(expires_dt) >= 14:
            try:
                self._token_expires_at = datetime.strptime(expires_dt[:14], "%Y%m%d%H%M%S").replace(tzinfo=KST)
            except ValueError:
                self._token_expires_at = now + timedelta(hours=12)
        else:
            self._token_expires_at = now + timedelta(hours=12)

        self._token = str(token)
        return self._token

    def buy_stock(self) -> dict[str, Any]:
        payload = {
            "dmst_stex_tp": self.config.exchange,
            "stk_cd": self.config.stock_code,
            "ord_qty": self.config.quantity,
            "ord_uv": self.config.order_price,
            "trde_tp": self.config.trade_type,
            "cond_uv": self.config.condition_price,
        }

        if self.config.dry_run:
            return {
                "dry_run": True,
                "message": "Real Kiwoom order was not sent.",
                "request": payload,
            }

        if self.config.env == "real" and self.config.confirm_live_order != LIVE_CONFIRM_PHRASE:
            raise RuntimeError(
                "Live order safety check failed. "
                f"Set KIWOOM_CONFIRM_LIVE_ORDER={LIVE_CONFIRM_PHRASE} to enable real orders."
            )

        token = self.issue_token()
        headers = {
            "authorization": f"Bearer {token}",
            "api-id": "kt10000",
        }
        return self._post_json("/api/dostk/ordr", payload, headers=headers)

    def _post_json(self, path: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        request_headers = {
            "Content-Type": "application/json;charset=UTF-8",
            **headers,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kiwoom HTTP error {exc.code}: {body}") from exc
        except URLError as exc:
            raise RuntimeError(f"Kiwoom network error: {exc}") from exc

        if not body:
            return {}

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Kiwoom returned non-JSON response: {body}") from exc

        return_code = data.get("return_code")
        if return_code not in (None, 0, "0"):
            raise RuntimeError(f"Kiwoom API error: {data}")
        return data


def load_config() -> Config:
    load_dotenv(Path.cwd() / ".env")

    dry_run = env_bool("KIWOOM_DRY_RUN", default=True)
    env = os.getenv("KIWOOM_ENV", "mock").strip().lower()

    app_key = os.getenv("KIWOOM_APP_KEY", "").strip()
    secret_key = os.getenv("KIWOOM_SECRET_KEY", "").strip()
    if not dry_run and (not app_key or not secret_key):
        raise RuntimeError("KIWOOM_APP_KEY and KIWOOM_SECRET_KEY are required when KIWOOM_DRY_RUN=false.")

    cwd = Path.cwd()
    return Config(
        app_key=app_key,
        secret_key=secret_key,
        env=env,
        dry_run=dry_run,
        confirm_live_order=os.getenv("KIWOOM_CONFIRM_LIVE_ORDER", "").strip(),
        stock_code=os.getenv("KIWOOM_STOCK_CODE", "005930").strip(),
        quantity=os.getenv("KIWOOM_QUANTITY", "1").strip(),
        exchange=os.getenv("KIWOOM_EXCHANGE", "KRX").strip().upper(),
        trade_type=os.getenv("KIWOOM_TRADE_TYPE", "3").strip(),
        order_price=os.getenv("KIWOOM_ORDER_PRICE", "").strip(),
        condition_price=os.getenv("KIWOOM_CONDITION_PRICE", "").strip(),
        order_time=parse_order_time(os.getenv("KIWOOM_ORDER_TIME", "15:00")),
        max_lateness_minutes=int(os.getenv("KIWOOM_MAX_LATENESS_MINUTES", "15")),
        holidays=parse_holidays(os.getenv("KIWOOM_HOLIDAYS", "")),
        log_path=Path(os.getenv("KIWOOM_LOG_PATH", cwd / "orders.jsonl")),
        state_path=Path(os.getenv("KIWOOM_STATE_PATH", cwd / ".kiwoom_samsung_state.json")),
    )


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_order_time(raw: str) -> dt_time:
    try:
        hour, minute = raw.strip().split(":", 1)
        return dt_time(hour=int(hour), minute=int(minute), tzinfo=KST)
    except ValueError as exc:
        raise ValueError("KIWOOM_ORDER_TIME must be HH:MM, for example 15:00.") from exc


def parse_holidays(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def now_kst() -> datetime:
    return datetime.now(KST)


def is_trading_day(day: datetime, holidays: set[str]) -> bool:
    return day.weekday() < 5 and day.date().isoformat() not in holidays


def target_datetime(day: datetime, target: dt_time) -> datetime:
    return datetime.combine(day.date(), target, tzinfo=KST)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def attempt_buy(config: Config, reason: str) -> dict[str, Any]:
    client = KiwoomRestClient(config)
    started_at = now_kst()
    record: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "reason": reason,
        "env": config.env,
        "dry_run": config.dry_run,
        "stock_code": config.stock_code,
        "quantity": config.quantity,
    }

    try:
        response = client.buy_stock()
        record.update({"status": "ok", "response": response})
        return record
    except Exception as exc:
        record.update({"status": "error", "error": str(exc)})
        return record
    finally:
        record["finished_at"] = now_kst().isoformat()
        append_log(config.log_path, record)


def run_once(config: Config) -> int:
    record = attempt_buy(config, "manual-once")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["status"] == "ok" else 1


def run_due(config: Config) -> int:
    current = now_kst()
    today = current.date().isoformat()
    target = target_datetime(current, config.order_time)
    late_limit = target + timedelta(minutes=config.max_lateness_minutes)
    state = load_state(config.state_path)

    record_base = {
        "started_at": current.isoformat(),
        "finished_at": current.isoformat(),
        "reason": "scheduled-due",
        "env": config.env,
        "dry_run": config.dry_run,
        "stock_code": config.stock_code,
        "quantity": config.quantity,
    }

    if not is_trading_day(current, config.holidays):
        record = {
            **record_base,
            "status": "skipped-non-trading-day",
            "message": "Today is a weekend or configured holiday.",
        }
        append_log(config.log_path, record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    if state.get("last_attempt_date") == today:
        record = {
            **record_base,
            "status": "skipped-already-attempted",
            "message": "An order attempt was already recorded for today.",
        }
        append_log(config.log_path, record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    if not (target <= current <= late_limit):
        record = {
            **record_base,
            "status": "skipped-outside-window",
            "target_time": target.isoformat(),
            "late_limit": late_limit.isoformat(),
        }
        append_log(config.log_path, record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    record = attempt_buy(config, "scheduled-due")
    save_state(
        config.state_path,
        {
            "last_attempt_date": today,
            "last_attempt_status": record["status"],
            "last_attempt_at": record["finished_at"],
        },
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["status"] == "ok" else 1


def run_schedule(config: Config) -> int:
    print(
        "Scheduler started: "
        f"{config.stock_code} {config.quantity} share(s), "
        f"{config.order_time.strftime('%H:%M')} KST, "
        f"dry_run={config.dry_run}, env={config.env}"
    )
    state = load_state(config.state_path)

    while True:
        current = now_kst()
        today = current.date().isoformat()
        target = target_datetime(current, config.order_time)
        late_limit = target + timedelta(minutes=config.max_lateness_minutes)
        already_attempted = state.get("last_attempt_date") == today

        if not is_trading_day(current, config.holidays):
            sleep_until_next_minute(current)
            continue

        if already_attempted:
            sleep_until_next_minute(current)
            continue

        if target <= current <= late_limit:
            record = attempt_buy(config, "scheduled")
            state = {
                "last_attempt_date": today,
                "last_attempt_status": record["status"],
                "last_attempt_at": record["finished_at"],
            }
            save_state(config.state_path, state)
            print(json.dumps(record, ensure_ascii=False))
            sleep_until_next_minute(current)
            continue

        if current > late_limit:
            state = {
                "last_attempt_date": today,
                "last_attempt_status": "skipped-late",
                "last_attempt_at": current.isoformat(),
            }
            save_state(config.state_path, state)
            append_log(
                config.log_path,
                {
                    "started_at": current.isoformat(),
                    "finished_at": current.isoformat(),
                    "reason": "scheduled",
                    "status": "skipped-late",
                    "message": "Current time is outside the configured order window.",
                    "target_time": target.isoformat(),
                    "late_limit": late_limit.isoformat(),
                },
            )
            sleep_until_next_minute(current)
            continue

        seconds_to_target = max(1, int((target - current).total_seconds()))
        time.sleep(min(seconds_to_target, 60))


def sleep_until_next_minute(current: datetime) -> None:
    time.sleep(max(1, 60 - current.second))


def main() -> int:
    parser = argparse.ArgumentParser(description="Buy 1 share of Samsung Electronics with Kiwoom REST API.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one buy attempt immediately.")
    mode.add_argument("--due", action="store_true", help="Run only if the configured order window is due now.")
    mode.add_argument("--schedule", action="store_true", help="Run continuously and buy once per trading day.")
    args = parser.parse_args()

    try:
        config = load_config()
        if args.due:
            return run_due(config)
        if args.schedule:
            return run_schedule(config)
        return run_once(config)
    except KeyboardInterrupt:
        print("Stopped.")
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
