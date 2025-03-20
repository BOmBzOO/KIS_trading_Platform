"""VI 모니터링"""

import asyncio
import logging
from typing import Any, Dict, Set
from datetime import datetime
from app.auth.models import AccountInfo
from app.common.constants import VIConfig
from app.strategy.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VITrading(BaseStrategy):
    """VI 모니터링"""
    
    def __init__(
            self,
            strategy_name: str = None,
            account_info: AccountInfo = None
        ):
        """초기화
        
        Args:
            strategy_name: 전략 이름
            account_info: 계좌 정보
        """
        super().__init__(strategy_name=strategy_name, account_info=account_info)
        self.active_symbols: Set[str] = set()
        self._closed = False

    async def initialize(self):
        pass
            
    async def start_monitoring(self):
        """VI 모니터링 시작"""
        try:
            # 1. WebSocket 연결
            await self.ws_client.connect()
            logger.info("WebSocket 연결이 설정되었습니다.")
            
            # 2. VI 데이터 구독
            await self.ws_client.subscribe_vi_stock()
            logger.info("VI 데이터 구독을 시작합니다.")
            
            # 3. 데이터 수신 대기
            while not self._closed:
                try:
                    vi_stock = await self.ws_client.receive_vi_stock()
                    await self.ws_client.subscribe_stock_ccld(vi_stock)
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
            
            # 3. 리소스 정리
            self.active_symbols.clear()
            logger.info("✅ VI 모니터링이 완전히 종료되었습니다.")


    async def process_data(self, data: Dict[str, Any]) -> None:
        """데이터 처리
        
        Args:
            data: 처리할 데이터 딕셔너리
        """
        await self.process_vi_data(data)

    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.ws_client:
                await self.ws_client.close()
            logger.info("리소스가 정리되었습니다.")
        except Exception as e:
            logger.error(f"리소스 정리 중 오류 발생: {str(e)}")
            raise 