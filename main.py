"""VI 모니터링 메인 스크립트"""

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from app.common.logger import setup_logger
from app.strategy.vi.vi_strategy import VITrading
from app.auth.auth_service import AuthService
from app.common.constants import APIConfig, EnvKeys
from app.auth.models import AccountInfo
from datetime import datetime

logger = logging.getLogger(__name__)

async def main():
    """메인 함수"""
    try:
        # 환경 변수 로드
        load_dotenv()
        
        # 로거 설정
        setup_logger()

        # 인증 서비스 초기화
        auth_service = AuthService()
        await auth_service.initialize()
        account_info_auth = await auth_service.authenticate()

        # VI 모니터 초기화
        logger.info("전략 프로그램을 시작합니다.")
        strategy = VITrading(strategy_name="VI trading", account_info=account_info_auth)
        await strategy.start_monitoring()
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        
    finally:
        # 리소스 정리
        if 'auth_service' in locals():
            await auth_service.close()
        logger.info("프로그램을 종료합니다.")

if __name__ == "__main__":
    try:
        # asyncio 이벤트 루프 실행
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {str(e)}") 