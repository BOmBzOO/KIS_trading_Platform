"""설정 관리"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from .constants import EnvKeys
from .utils import get_env_or_raise

@dataclass
class Config:
    """애플리케이션 설정"""
    external_username: str
    external_password: str
    account_number: str
    
    @classmethod
    def load(cls, env_path: Optional[Path] = None) -> 'Config':
        """설정을 로드합니다.
        
        Args:
            env_path: .env 파일 경로 (기본값: None)
            
        Returns:
            Config: 설정 객체
            
        Raises:
            ValueError: 필수 환경 변수가 설정되지 않은 경우
        """
        logger = logging.getLogger("Config")
        
        if env_path and not env_path.exists():
            logger.warning(f"지정된 .env 파일을 찾을 수 없습니다: {env_path}")
            
        load_dotenv(dotenv_path=env_path if env_path else None)
        
        try:
            return cls(
                external_username=get_env_or_raise(EnvKeys.EXTERNAL_USERNAME),
                external_password=get_env_or_raise(EnvKeys.EXTERNAL_PASSWORD),
                account_number=get_env_or_raise(EnvKeys.ACCOUNT_NUMBER)
            )
        except ValueError as e:
            logger.error(f"설정 로드 실패: {str(e)}")
            raise 