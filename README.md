# Kiwoom Samsung Daily Buy

키움증권 REST API로 삼성전자(`005930`) 1주를 매일 정해진 시간에 매수하는 최소 자동화 예제입니다.

기본값은 `KIWOOM_DRY_RUN=true`라서 실제 주문을 보내지 않습니다.

## 1. 설정

`.env.example`을 `.env`로 복사한 뒤 값을 채우거나, PowerShell에서 필요한 환경변수를 지정합니다.

```powershell
$env:KIWOOM_DRY_RUN="true"
$env:KIWOOM_ENV="mock"
$env:KIWOOM_ORDER_TIME="15:00"
```

실제 주문을 보낼 때만 아래처럼 바꿉니다.

```powershell
$env:KIWOOM_DRY_RUN="false"
$env:KIWOOM_ENV="real"
$env:KIWOOM_APP_KEY="발급받은_APP_KEY"
$env:KIWOOM_SECRET_KEY="발급받은_SECRET_KEY"
$env:KIWOOM_CONFIRM_LIVE_ORDER="BUY_SAMSUNG_005930_DAILY"
```

모의투자 API로 주문 요청을 보내려면 `KIWOOM_ENV="mock"` 상태에서 `KIWOOM_DRY_RUN="false"`로 바꾸면 됩니다. 실계좌(`real`)만 추가 확인 문구가 필요합니다.

## 2. 즉시 1회 테스트

```powershell
python .\samsung_daily_buy.py --once
```

`dry_run=true` 상태에서는 주문 payload만 `orders.jsonl`에 기록됩니다.

현재 PC에서 `python` 명령이 인식되지 않으면 Python 3.10 이상을 설치한 뒤 "Add python.exe to PATH"를 켜거나, 설치된 `python.exe`의 전체 경로로 실행하세요.

## 3. 매일 15:00 KST에 실행

```powershell
python .\samsung_daily_buy.py --schedule
```

스케줄러는 월요일부터 금요일까지만 시도합니다. 국내 공휴일은 자동 판별하지 않으므로 필요하면 아래처럼 지정하세요.

```powershell
$env:KIWOOM_HOLIDAYS="2026-05-25,2026-08-17"
```

중복 주문 방지를 위해 하루에 한 번 시도하면 `.kiwoom_samsung_state.json`에 상태를 남깁니다.

PC를 계속 켜두기 어렵다면 Windows 작업 스케줄러에서 평일 15:00에 아래 명령이 실행되도록 등록하는 방식도 좋습니다.

```powershell
python .\samsung_daily_buy.py --once
```

클라우드 서버에서는 지연 실행을 막기 위해 아래처럼 `--due`를 쓰는 편이 안전합니다. 현재 시간이 설정된 주문 창 안일 때만 매수 시도하고, 그 밖에는 skip 로그만 남깁니다.

```powershell
python .\samsung_daily_buy.py --due
```

Oracle Cloud 배포용 systemd 예시는 [deploy/oracle/README.md](deploy/oracle/README.md)에 있습니다.

## 4. 주문 기본값

- 종목: 삼성전자 보통주 `005930`
- 수량: `1`
- 거래소: `KRX`
- 주문: 시장가, `trde_tp=3`
- API: `kt10000`, `/api/dostk/ordr`

실거래 전에는 키움 REST API 사용 신청, 앱키/시크릿 발급, 모의투자 테스트, 주문 가능 시간 확인을 먼저 끝내세요.
