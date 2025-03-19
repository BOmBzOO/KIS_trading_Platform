"""VI 모니터링"""

import asyncio
import logging
from typing import Any, Dict, Set
from datetime import datetime
from app.auth.models import AccountInfo
from app.common.constants import VIConfig
from app.auth.auth_service import AuthService
from app.strategy.base.service.websocket import KISWebSocketClient

logger = logging.getLogger(__name__)

class VIMonitor:
    """VI 모니터링"""
    
    def __init__(self):
        """초기화"""
        self.auth_service = AuthService()
        self.ws_client = None
        self.account_info = None
        self.active_symbols: Set[str] = set()
        self._closed = False
        
    async def initialize(self):
        """외부 서버 인증 및 계좌 정보 초기화"""
        try:
            # 1. 인증 서비스 초기화
            await self.auth_service.initialize()
            
            # 2. 외부 서버 인증 및 계좌 정보 조회 (저장된 정보 사용 또는 새로운 인증)
            self.account_info = await self.auth_service.authenticate()
            logger.info(f"계좌 정보 로드 완료 (계좌: {self.account_info.cano})")
            logger.info(f"계좌 타입: {'실전' if self.account_info.is_live else '모의'}")
            
            # 3. WebSocket 클라이언트 초기화
            self.ws_client = KISWebSocketClient(self.account_info)
            
        except Exception as e:
            logger.error(f"초기화 중 오류 발생: {str(e)}")
            raise
            
    async def start_monitoring(self):
        """VI 모니터링 시작"""
        try:
            # 1. WebSocket 연결
            await self.ws_client.connect()
            logger.info("WebSocket 연결이 설정되었습니다.")
            
            # 2. VI 데이터 구독
            await self.ws_client.subscribe_vi_data()
            logger.info("VI 데이터 구독을 시작합니다.")
            
            # 3. 데이터 수신 대기
            while not self._closed:
                try:
                    data = await self.ws_client.receive_data()
                    await self.process_vi_data(data)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"데이터 수신 중 오류 발생: {str(e)}")
                    continue
                
        except asyncio.CancelledError:
            logger.info("VI 모니터링이 취소되었습니다.")
        except Exception as e:
            logger.error(f"모니터링 중 오류 발생: {str(e)}")
        finally:
            await self.stop()
            
    async def process_vi_data(self, data: Dict[str, Any]):
        """VI 데이터 처리
        
        Args:
            data: VI 발동 데이터
        """
        try:
            # 1. 기본 정보 추출
            symbol = data.get("stck_shrn_iscd", "")
            trigger_time = data.get("vi_trgr_time", "")
            trigger_price = data.get("vi_trgr_prpr", "")
            
            # 2. VI 발동 정보 로깅
            logger.info(f"⚡ VI 발동: {symbol}")
            logger.info(f"  - 시각: {trigger_time}")
            logger.info(f"  - 가격: {trigger_price}")
            
            # 3. VI 발동 종목 추적
            if symbol and symbol not in self.active_symbols:
                self.active_symbols.add(symbol)
                logger.info(f"새로운 VI 발동 종목이 추가되었습니다: {symbol}")
                
            # TODO: 추가적인 데이터 처리 로직 구현
            
        except Exception as e:
            logger.error(f"VI 데이터 처리 중 오류 발생: {str(e)}")
            
    async def stop(self) -> None:
        """모니터링 종료"""
        if not self._closed:
            self._closed = True
            logger.info("VI 모니터링을 종료합니다.")
            
            # 1. WebSocket 연결 종료
            if self.ws_client:
                await self.ws_client.disconnect()
                logger.info("WebSocket 연결이 종료되었습니다.")
            
            # 2. 인증 서비스 종료
            await self.auth_service.close()
            logger.info("인증 서비스가 종료되었습니다.")
            
            # 3. 리소스 정리
            self.active_symbols.clear()
            logger.info("✅ VI 모니터링이 완전히 종료되었습니다.") 