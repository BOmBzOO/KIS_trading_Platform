"""인증 관련 모델"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class AccountInfo:
    """계좌 정보"""
    kis_access_token: str
    access_token_expired: datetime
    hts_id: str
    app_key: str
    app_secret: str
    cano: str
    approval_key: Optional[str] = None
    is_live: bool = True
    acnt_prdt_cd: str = "01"
    acnt_type: str = "live"
    acnt_name: str = ""
    owner_name: str = ""
    owner_id: str = ""
    id: str = ""
    discord_webhook_url: str = ""
    is_active: bool = True
    
    @classmethod
    def from_dict(cls, data: dict) -> "AccountInfo":
        """딕셔너리에서 AccountInfo 객체 생성
        
        Args:
            data: 계좌 정보 딕셔너리
            
        Returns:
            AccountInfo: 계좌 정보 객체
        """
        return cls(
            kis_access_token=data.get("kis_access_token", ""),
            access_token_expired=data.get("access_token_expired", datetime.now()),
            hts_id=data.get("hts_id", ""),
            app_key=data.get("app_key", ""),
            app_secret=data.get("app_secret", ""),
            cano=data.get("cano", ""),
            approval_key=data.get("approval_key"),
            is_live=data.get("is_live", True),
            acnt_prdt_cd=data.get("acnt_prdt_cd", "01"),
            acnt_type=data.get("acnt_type", "live"),
            acnt_name=data.get("acnt_name", ""),
            owner_name=data.get("owner_name", ""),
            owner_id=data.get("owner_id", ""),
            id=data.get("id", ""),
            discord_webhook_url=data.get("discord_webhook_url", ""),
            is_active=data.get("is_active", True)
        ) 