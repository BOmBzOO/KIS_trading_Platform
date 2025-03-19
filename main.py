"""VI 모니터링 메인 스크립트"""

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from app.common.logger import setup_logger
from app.strategy.vi.strategy import VIMonitor
from app.auth.auth_service import AuthService
from app.common.constants import APIConfig, EnvKeys

logger = logging.getLogger(__name__)

async def main():
    """메인 함수"""
    try:
        
        # 인증 서비스 초기화 및 계좌 정보 조회
        auth_service = AuthService()
        await auth_service.initialize()
        logger.info("인증 서비스가 초기화되었습니다.")
        
        # 외부 서버 로그인 및 계좌 정보 조회
        account_info = await auth_service.authenticate()
        logger.info(f"계좌 정보 조회 성공 (계좌: {account_info.cano})")
        logger.info(f"계좌 타입: {'실전' if account_info.is_live else '모의'}")
        
        # VI 모니터 초기화
        logger.info("VI 모니터링 프로그램을 시작합니다.")
        monitor = VIMonitor()
        await monitor.initialize()
        logger.info("VI 모니터가 초기화되었습니다.")
        
        # 시그널 핸들러 설정
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(monitor.stop()))
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(monitor.stop()))
        logger.info("시그널 핸들러가 설정되었습니다.")
        
        # VI 모니터링 시작
        logger.info("VI 모니터링을 시작합니다...")
        await monitor.start_monitoring()
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        if 'monitor' in locals():
            await monitor.stop()
        
    finally:
        # 8. 리소스 정리
        if 'auth_service' in locals():
            await auth_service.close()
        logger.info("프로그램을 종료합니다.")

if __name__ == "__main__":
    try:
        setup_logger()
        load_dotenv()
        
        required_env = [EnvKeys.EXTERNAL_USERNAME, EnvKeys.EXTERNAL_PASSWORD, EnvKeys.CANO]
        missing_env = [key for key in required_env if not os.getenv(key)]
        if missing_env:
            logger.error(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_env)}")
            exit(1)
            
        logger.info("환경 변수 확인 완료")
        
        # asyncio 이벤트 루프 실행
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {str(e)}") 