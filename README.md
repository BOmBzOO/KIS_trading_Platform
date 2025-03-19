# VI 트레이딩 시스템

한국투자증권 API를 활용한 VI(Volatility Interruption) 트레이딩 자동화 시스템입니다.

## 주요 기능

- VI 발동 종목 실시간 감지
- VI 해제 후 자동 매매 실행
- 실시간 포지션 관리
- Discord를 통한 알림
- 계좌 모니터링

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/vi-trading.git
cd vi-trading
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
`.env` 파일을 생성하고 다음 정보를 입력합니다:
```
APP_KEY=your_app_key
APP_SECRET=your_app_secret
DISCORD_WEBHOOK_URL=your_discord_webhook_url
```

## 사용 방법

1. 프로그램 실행
```bash
python main.py
```

2. 로그 확인
- `logs/trading.log` 파일에서 상세 로그 확인 가능
- Discord를 통한 실시간 알림 수신

## 프로젝트 구조

```
vi-trading/
├── app/
│   ├── api/           # API 관련 모듈
│   ├── core/          # 핵심 기능 모듈
│   ├── models/        # 데이터 모델
│   ├── strategy/      # 트레이딩 전략
│   └── utils/         # 유틸리티 함수
├── logs/              # 로그 파일
├── tests/             # 테스트 코드
├── .env              # 환경 변수
├── .gitignore        # Git 제외 파일
├── main.py           # 메인 실행 파일
├── README.md         # 프로젝트 설명
└── requirements.txt   # 의존성 목록
```

## 주의사항

- 실제 거래 전에 충분한 테스트를 진행하세요.
- API 키와 시크릿은 안전하게 관리하세요.
- 거래에 따른 손실은 본인 책임입니다.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request "# KIS_trading_Platform"  "# KIS_trading_Platform" 
