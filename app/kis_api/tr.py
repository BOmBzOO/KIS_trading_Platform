"""인증 관련 서비스"""

import json
import logging
import requests
from datetime import datetime, timedelta
from app.auth.models import AccountInfo
from app.common.constants import APIConfig

logger = logging.getLogger("AuthService")

def get_approval_key(app_key: str, app_secret: str, is_live: bool = True) -> str:
    """웹소켓 연결을 위한 approval_key 발급"""
    try:
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret
        }
        
        # 실전/모의 도메인 선택
        base_url = APIConfig.KIS_BASE_URL_LIVE if is_live else APIConfig.KIS_BASE_URL_PAPER
        url = f"{base_url}/oauth2/Approval"
        
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()  # HTTP 오류 체크
        
        approval_key = response.json()["approval_key"]
        return approval_key
        
    except requests.exceptions.RequestException as e:
        raise 