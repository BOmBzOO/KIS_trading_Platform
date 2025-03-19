"""공통 상수 정의"""

from pathlib import Path
from typing import Final

# 프로젝트 경로 관련 상수
PROJECT_ROOT: Final = Path(__file__).parent.parent.parent
APP_DIR: Final = PROJECT_ROOT / "app"

class APIConfig:
    """API 관련 설정"""
    # 외부 API 설정
    KIS_BASE_URL_LIVE: Final = "https://openapi.koreainvestment.com:9443"
    KIS_BASE_URL_PAPER: Final = "https://openapivts.koreainvestment.com:29443"
    
    # KIS API 설정
    KIS_WEBSOCKET_URL: Final = "ws://ops.koreainvestment.com:21000"  # 실전 웹소켓
    KIS_WEBSOCKET_URL_LIVE: Final = "ws://ops.koreainvestment.com:21000"  # 실전 웹소켓 URL
    KIS_WEBSOCKET_URL_PAPER: Final = "ws://ops.koreainvestment.com:31000"  # 모의 웹소켓
    
    EXTERNAL_BASE_URL: Final = "http://bombzoo-home.iptime.org:8000"
    EXTERNAL_API_PATH: Final = "/api/v1"
    EXTERNAL_LOGIN_PATH: Final = f"{EXTERNAL_API_PATH}/login/access-token"
    EXTERNAL_ACCOUNTS_PATH: Final = f"{EXTERNAL_API_PATH}/accounts"
    
class WebSocketConfig:
    """웹소켓 관련 설정"""
    PING_INTERVAL: Final = 60  # 초
    TIMEOUT: Final = 30        # 초
    MAX_RETRY_COUNT: Final = 3
    RETRY_DELAY: Final = 5     # 초
    
class VIConfig:
    """VI 관련 설정"""
    REALTIME_TR: Final = "H0STCNT0"  # VI 발동 실시간 조회 TR 코드
    TRADE_TR: Final = "H0STASP0"    # 실시간 체결 정보 TR 코드
    
    # 웹소켓 메시지 타입
    MSG_TYPE_SUBSCRIBE: Final = "1"     # 구독 요청
    MSG_TYPE_UNSUBSCRIBE: Final = "2"   # 구독 해지
    
    CHECK_INTERVAL: Final = 1  # 초
    MAX_RETRIES: Final = 3     # 최대 재시도 횟수
    
class LogConfig:
    """로깅 관련 설정"""
    DIR: Final[Path] = APP_DIR / "logs"  # 로그 디렉토리 경로
    FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    FILENAME: Final[str] = "vi_monitor.log"
    LEVEL: Final[str] = "INFO"
    
class EnvKeys:
    """환경 변수 키"""
    EXTERNAL_USERNAME: Final[str] = "EXTERNAL_USERNAME"
    EXTERNAL_PASSWORD: Final[str] = "EXTERNAL_PASSWORD"
    KIS_ACCESS_TOKEN: Final[str] = "KIS_ACCESS_TOKEN"
    ACCESS_TOKEN_EXPIRED: Final[str] = "ACCESS_TOKEN_EXPIRED"
    APPROVAL_KEY: Final[str] = "APPROVAL_KEY"
    HTS_ID: Final[str] = "HTS_ID"
    ACCOUNT_NUMBER: Final[str] = "ACCOUNT_NUMBER"
    APP_KEY: Final[str] = "APP_KEY"
    APP_SECRET: Final[str] = "APP_SECRET"
    CANO: Final[str] = "CANO"
    IS_LIVE: Final[str] = "IS_LIVE"
    ACNT_PRDT_CD: Final[str] = "ACNT_PRDT_CD"
    ACNT_TYPE: Final[str] = "ACNT_TYPE"
    ACNT_NAME: Final[str] = "ACNT_NAME"
    DISCORD_WEBHOOK_URL: Final[str] = "DISCORD_WEBHOOK_URL"
    OWNER_NAME: Final[str] = "OWNER_NAME"
    OWNER_ID: Final[str] = "OWNER_ID"
    ID: Final[str] = "ID"

class DateTimeConfig:
    """날짜/시간 관련 상수"""
    DATE_FORMAT: Final[str] = "%Y%m%d"
    TIME_FORMAT: Final[str] = "%H%M%S"
    DATETIME_FORMAT: Final[str] = f"{DATE_FORMAT}_{TIME_FORMAT}" 