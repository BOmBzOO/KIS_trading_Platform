"""유틸리티 함수"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime, time
from dotenv import load_dotenv, set_key

def is_market_open() -> bool:
    """장 운영 시간 여부를 확인합니다."""
    now = datetime.now().time()
    market_start = time(9, 0)  # 09:00
    market_end = time(15, 30)  # 15:30
    return market_start <= now <= market_end

def ensure_directory(path: Path) -> None:
    """디렉토리가 없으면 생성합니다."""
    path.mkdir(parents=True, exist_ok=True)
    
def load_env_file(env_path: Optional[Path] = None) -> None:
    """환경 변수 파일 로드"""
    if env_path is None:
        env_path = Path(".env")
    load_dotenv(env_path)

def save_account_info_to_env(
    kis_access_token: str,
    access_token_expired: str,
    approval_key: str,
    hts_id: str,
    app_key: str,
    app_secret: str,
    cano: str,
    is_live: bool = True,
    acnt_prdt_cd: str = "01",
    acnt_type: str = "live",
    acnt_name: str = "",
    owner_name: str = "",
    owner_id: str = "",
    id: str = "",
    discord_webhook_url: str = "",
    is_active: bool = True
) -> None:
    """계좌 정보를 .env 파일에 저장
    
    Args:
        kis_access_token: KIS API 액세스 토큰
        access_token_expired: 토큰 만료 시간
        approval_key: 웹소켓 승인 키
        hts_id: HTS ID
        app_key: 앱 키
        app_secret: 앱 시크릿
        cano: 계좌번호
        is_live: 실계좌 여부 (기본값: True)
        acnt_prdt_cd: 계좌상품코드 (기본값: "01")
        acnt_type: 계좌유형 (기본값: "live")
        acnt_name: 계좌명 (기본값: "")
        owner_name: 소유자명 (기본값: "")
        owner_id: 소유자ID (기본값: "")
        id: 계좌ID (기본값: "")
        discord_webhook_url: 디스코드 웹훅 URL (기본값: "")
        is_active: 활성화 여부 (기본값: True)
    """
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수 업데이트
    env_vars = {
        "KIS_ACCESS_TOKEN": kis_access_token,
        "ACCESS_TOKEN_EXPIRED": access_token_expired,
        "APPROVAL_KEY": approval_key,
        "HTS_ID": hts_id,
        "APP_KEY": app_key,
        "APP_SECRET": app_secret,
        "CANO": cano,
        "IS_LIVE": str(is_live).lower(),
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "ACNT_TYPE": acnt_type,
        "ACNT_NAME": acnt_name,
        "OWNER_NAME": owner_name,
        "OWNER_ID": owner_id,
        "ID": id,
        "DISCORD_WEBHOOK_URL": discord_webhook_url,
        "IS_ACTIVE": str(is_active).lower()
    }
    
    # .env 파일 업데이트
    env_path = Path(".env")
    
    # 기존 내용 읽기
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []
        
    # 환경 변수 업데이트
    updated_vars = set()
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("#"):
            key = line.split("=")[0].strip()
            if key in env_vars:
                lines[i] = f"{key}={env_vars[key]}\n"
                updated_vars.add(key)
                
    # 없는 변수 추가
    for key, value in env_vars.items():
        if key not in updated_vars:
            lines.append(f"{key}={value}\n")
            
    # 파일 저장
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def get_env_or_raise(key: str) -> str:
    """환경 변수를 가져오거나 예외를 발생시킵니다."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"필수 환경 변수가 설정되지 않았습니다: {key}")
    return value

def format_number(value: float, decimal_places: int = 2) -> str:
    """숫자를 포맷팅합니다."""
    return f"{value:,.{decimal_places}f}"

def parse_datetime(datetime_str: str, format: str = "%Y%m%d%H%M%S") -> datetime:
    """문자열을 datetime으로 변환합니다."""
    try:
        return datetime.strptime(datetime_str, format)
    except ValueError as e:
        raise ValueError(f"날짜/시간 형식이 올바르지 않습니다: {datetime_str}") from e 