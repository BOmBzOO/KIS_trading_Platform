# VI 모니터링 프로그램

한국투자증권 API를 활용한 VI(Volatility Interruption) 모니터링 프로그램입니다.

## 주요 기능

- VI 발동/해제 실시간 모니터링
- VI 종목 실시간 체결 정보 수신
- 웹소켓을 통한 실시간 데이터 처리
- 외부 서버 인증 및 계좌 정보 관리

## 시스템 요구사항

- Python 3.8 이상
- 한국투자증권 실전/모의 계좌
- 외부 인증 서버 접근 권한

## 설치 방법

1. 저장소 클론
```bash
git clone [repository_url]
cd VI_trading
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
`.env` 파일을 생성하고 다음 정보를 설정:
```
EXTERNAL_USERNAME=your_username
EXTERNAL_PASSWORD=your_password
CANO=your_account_number
```

## 실행 방법

```bash
python main.py
```

## 프로젝트 구조

```
app/
├── auth/               # 인증 관련 모듈
├── common/             # 공통 유틸리티
├── strategy/
│   ├── base/          # 기본 전략 컴포넌트
│   └── vi/            # VI 모니터링 전략
└── main.py            # 메인 실행 파일
```

## 로깅

- 로그 파일은 `logs/` 디렉토리에 저장됩니다.
- 로그 레벨은 환경 변수 `LOG_LEVEL`로 설정 가능합니다.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request "# KIS_trading_Platform"  "# KIS_trading_Platform" 
