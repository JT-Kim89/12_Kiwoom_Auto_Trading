# Oracle Cloud 배포 가이드

이 폴더는 Oracle Cloud VM에서 삼성전자 1주 매수 봇을 매일 15:00 KST에 실행하기 위한 systemd 설정입니다.

## 전체 흐름

1. Oracle Cloud 계정 생성
2. Always Free 가능 VM 생성
3. Reserved Public IP 생성 후 VM에 연결
4. VM의 공인 IP를 키움 REST API App Key 관리 화면에 등록
5. 이 프로젝트 파일을 VM에 업로드
6. `deploy/oracle/setup.sh` 실행
7. `.env`에 키움 App Key/Secret 설정
8. 모의투자 → 실계좌 순서로 테스트

## VM 권장값

- 이미지: Oracle Linux 또는 Ubuntu
- Shape: Always Free 가능 AMD 또는 Ampere A1
- 네트워크: Public subnet, SSH 접속 허용
- 공인 IP: Reserved Public IP 권장

## 서버 준비

서버에 접속한 뒤 프로젝트를 `~/repo` 같은 폴더에 올리고 실행합니다.

```bash
cd ~/repo
chmod +x deploy/oracle/setup.sh
deploy/oracle/setup.sh
```

설치 후 설정 파일을 수정합니다.

```bash
nano ~/kiwoom-samsung-buy/.env
```

처음에는 반드시 아래 상태로 시작하세요.

```env
KIWOOM_DRY_RUN=true
KIWOOM_ENV=mock
```

모의투자 API 주문 요청까지 테스트할 때:

```env
KIWOOM_DRY_RUN=false
KIWOOM_ENV=mock
KIWOOM_APP_KEY=모의투자_APP_KEY
KIWOOM_SECRET_KEY=모의투자_SECRET_KEY
```

실계좌 전환 시:

```env
KIWOOM_DRY_RUN=false
KIWOOM_ENV=real
KIWOOM_APP_KEY=실전_APP_KEY
KIWOOM_SECRET_KEY=실전_SECRET_KEY
KIWOOM_CONFIRM_LIVE_ORDER=BUY_SAMSUNG_005930_DAILY
```

## 확인 명령

```bash
systemctl list-timers kiwoom-samsung-buy.timer
sudo systemctl status kiwoom-samsung-buy.timer
sudo systemctl start kiwoom-samsung-buy.service
journalctl -u kiwoom-samsung-buy.service -n 100 --no-pager
tail -f ~/kiwoom-samsung-buy/orders.jsonl
```

`kiwoom-samsung-buy.service`는 `--due` 모드로 실행되므로, 15:00~15:15 KST 주문 창 밖에서는 실제 주문하지 않고 skip 로그만 남깁니다.

## 중지

```bash
sudo systemctl disable --now kiwoom-samsung-buy.timer
```
