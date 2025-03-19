"""VI 모니터링 서비스"""

import asyncio
import json
import logging
from typing import Dict, AsyncGenerator
from datetime import datetime
from app.auth.models import AccountInfo
from app.common.constants import VIConfig, WebSocketConfig
from app.strategy.base.service.websocket import KISWebSocketClient


class VIWebSocketClient(KISWebSocketClient):
    """VI 모니터링을 위한 웹소켓 클라이언트"""

    def __init__(self, account_info: AccountInfo):
        super().__init__(account_info)
        self.vi_triggered_stocks: Dict[str, float] = {}  # 종목코드: VI 발동 시간
        self.logger = logging.getLogger("VIWebSocket")

    async def _subscribe_vi(self) -> bool:
        """VI 발동 정보 구독"""
        if not self.websocket or self._is_token_expired():
            self.logger.warning("웹소켓이 없거나 토큰이 만료됨")
            return False

        try:
            # VI 발동 구독
            success = await self.subscribe(VIConfig.REALTIME_TR)
            if not success:
                return False
            
            self.logger.info("VI 발동 구독 완료")
            return True
                
        except Exception as e:
            self.logger.error(f"VI 구독 요청 중 오류 발생: {str(e)}")
            return False

    async def _subscribe_realtime_trade(self, stock_code: str) -> bool:
        """VI 종목의 실시간 체결 정보 구독"""
        if not self.websocket or self._is_token_expired():
            self.logger.warning("웹소켓이 없거나 토큰이 만료됨")
            return False

        try:
            success = await self.subscribe(VIConfig.TRADE_TR, stock_code)
            if success:
                self.logger.info(f"실시간 체결 정보 구독 성공: {stock_code}")
            return success
                
        except Exception as e:
            self.logger.error(f"체결 정보 구독 요청 중 오류 발생: {str(e)}")
            return False

    async def subscribe_vi_data(self) -> AsyncGenerator[dict, None]:
        """VI 발동 및 해제 데이터 수신"""
        retry_count = 0
        last_reconnect = 0

        while not self._closed:
            try:
                if self._shutdown_event.is_set():
                    self.logger.info("종료 요청이 감지되었습니다.")
                    break
                    
                if not self.websocket:
                    current_time = datetime.now().timestamp()
                    
                    if current_time - last_reconnect < 5:
                        await asyncio.sleep(1)
                        continue
                        
                    if retry_count >= WebSocketConfig.MAX_RETRY_COUNT:
                        self.logger.error("최대 재연결 횟수 초과")
                        break

                    self.logger.warning("웹소켓 재연결 시도 중...")
                    if await self.connect():
                        retry_count = 0
                        if not await self._subscribe_vi():
                            self.logger.error("VI 구독 실패")
                            continue
                    else:
                        retry_count += 1
                        last_reconnect = current_time
                        await asyncio.sleep(WebSocketConfig.RETRY_DELAY)
                    continue

                try:
                    message = self.websocket.recv()
                except Exception as e:
                    if not self._closed:
                        self.logger.error(f"메시지 수신 중 오류: {str(e)}")
                    await asyncio.sleep(1)
                    continue

                self.logger.debug(f"수신된 메시지: {message}")

                if message == "PINGPONG":
                    self.logger.debug("[PINGPONG] 수신됨")
                    self._last_pong = datetime.now().timestamp()
                    continue

                if message[0] in ['0', '1']:
                    recvstr = message.split('|')
                    if len(recvstr) < 4:
                        self.logger.warning(f"잘못된 메시지 형식: {message}")
                        continue
                        
                    tr_id = recvstr[1]
                    data = None

                    if tr_id == VIConfig.REALTIME_TR:  # VI 발동
                        try:
                            data = self._parse_vi_data(recvstr[3])
                            stock_code = data["stck_shrn_iscd"]
                            self.logger.info(f"VI 발동 감지: {stock_code}")
                            self.vi_triggered_stocks[stock_code] = datetime.now().timestamp()
                            await self._subscribe_realtime_trade(stock_code)
                        except Exception as e:
                            self.logger.error(f"VI 데이터 파싱 오류: {str(e)}")

                    elif tr_id == "H0STASP0":  # 실시간 체결
                        try:
                            data = self._parse_trade_data(recvstr[3])
                            stock_code = data["stck_shrn_iscd"]
                            if stock_code in self.vi_triggered_stocks:
                                elapsed_time = datetime.now().timestamp() - self.vi_triggered_stocks[stock_code]
                                if elapsed_time > 120:  # 2분 경과
                                    self.logger.info(f"VI 해제 감지: {stock_code}")
                                    del self.vi_triggered_stocks[stock_code]
                        except Exception as e:
                            self.logger.error(f"체결 데이터 파싱 오류: {str(e)}")

                    if data:
                        yield data

            except asyncio.CancelledError:
                self.logger.info("웹소켓 수신 작업이 취소됨")
                break
            except Exception as e:
                if not self._closed:
                    self.logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
                await asyncio.sleep(1)

        await self.shutdown()
        self.logger.info("VI 데이터 구독이 종료되었습니다.")

    def _parse_vi_data(self, data: str) -> dict:
        """VI 발동 데이터 파싱"""
        fields = data.split('^')
        return {
            "stck_shrn_iscd": fields[0],  # 종목코드
            "vi_trgr_time": fields[1],    # VI 발동 시각
            "vi_trgr_prpr": fields[2]     # VI 발동 가격
        }

    def _parse_trade_data(self, data: str) -> dict:
        """실시간 체결 데이터 파싱"""
        fields = data.split('^')
        return {
            "stck_shrn_iscd": fields[0],  # 종목코드
            "stck_prpr": fields[2],       # 현재가
            "acml_vol": fields[13]        # 누적거래량
        } 