"""KIS 웹소켓 클라이언트"""

import asyncio
import json
import logging
from typing import Optional, Tuple
from datetime import datetime
import websocket
from app.auth.models import AccountInfo
from app.kis_api.tr import get_approval_key
from app.common.constants import APIConfig
from app.common.utils import save_account_info_to_env


class KISWebSocketClient:
    """KIS WebSocket 기본 클라이언트"""

    def __init__(self, account_info: AccountInfo):
        """초기화
        
        Args:
            account_info: 계좌 정보
        """
        self.account_info = account_info
        self.websocket: Optional[websocket.WebSocket] = None
        self._closed = False
        self.logger = logging.getLogger("KISWebSocket")
        self._last_pong = datetime.now().timestamp()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 5  # 초 단위
        self._is_connecting = False
        self._aes_key = None
        self._aes_iv = None
            
    async def connect(self) -> bool:
        """웹소켓 연결 수립"""
        if self._is_connecting:
            return False
            
        try:
            self._is_connecting = True
            if self.websocket:
                await self.close()
                
            self.websocket = websocket.WebSocket()
            ws_url = APIConfig.KIS_WEBSOCKET_URL if self.account_info.is_live else APIConfig.KIS_WEBSOCKET_URL_PAPER
            
            # 웹소켓 연결
            self.websocket.connect(ws_url, ping_interval=60)
            self.logger.info(f"✅ 웹소켓 연결 성공 ({'실전' if self.account_info.is_live else '모의'})")
            
            # HTS ID 구독
            await self._subscribe_hts()
            self._reconnect_attempts = 0  # 연결 성공 시 재연결 시도 횟수 초기화
            self._closed = False
            return True
            
        except Exception as e:
            self.logger.error(f"⚠ 웹소켓 연결 실패: {str(e)}")
            if self.websocket:
                self.websocket.close()
                self.websocket = None
            self._closed = True
            return False
        finally:
            self._is_connecting = False

    async def ensure_connection(self) -> bool:
        """웹소켓 연결 상태 확인 및 필요시 재연결
        
        Returns:
            bool: 연결 상태
        """
        if not self.websocket or self._closed:
            if self._reconnect_attempts < self._max_reconnect_attempts:
                self._reconnect_attempts += 1
                self.logger.info(f"웹소켓 재연결 시도 {self._reconnect_attempts}/{self._max_reconnect_attempts}")
                await asyncio.sleep(self._reconnect_delay)
                return await self.connect()
            else:
                self.logger.error("최대 재연결 시도 횟수 초과")
                return False
                
        try:
            # 연결 상태 확인을 위한 ping
            self.websocket.ping()
            return True
        except Exception as e:
            self.logger.error(f"웹소켓 연결 상태 확인 실패: {str(e)}")
            self._closed = True
            return await self.ensure_connection()

    def _process_response(self, data: str) -> Tuple[bool, Optional[dict]]:
        """응답 데이터 처리
        
        Args:
            data: 수신된 데이터
            
        Returns:
            Tuple[bool, Optional[dict]]: (성공 여부, 처리된 데이터)
        """
        try:
            # 실시간 데이터인 경우
            if data[0] in ['0', '1']:
                return True, None
                
            # JSON 응답인 경우
            json_data = json.loads(data)
            tr_id = json_data.get("header", {}).get("tr_id")
            
            # PINGPONG 처리
            if tr_id == "PINGPONG":
                self.logger.info(f"RECV [{tr_id}]")
                self.logger.info(f"SEND [{tr_id}]")
                return True, None
                
            # 일반 응답 처리
            rt_cd = json_data.get("body", {}).get("rt_cd")
            msg1 = json_data.get("body", {}).get("msg1", "")
            
            if rt_cd == '1':  # 에러
                self.logger.error(f"ERROR RETURN CODE [{rt_cd}] MSG [{msg1}]")
                return False, None
            elif rt_cd == '0':  # 정상
                self.logger.info(f"RETURN CODE [{rt_cd}] MSG [{msg1}]")
                
                # HTS ID 구독 응답 처리
                if tr_id in ["K0STCNI0", "K0STCNI9", "H0STCNI0", "H0STCNI9"]:
                    output = json_data.get("body", {}).get("output", {})
                    self._aes_key = output.get("key")
                    self._aes_iv = output.get("iv")
                    self.logger.info(f"TRID [{tr_id}] KEY[{self._aes_key}] IV[{self._aes_iv}]")
                    
                return True, json_data.get("body", {}).get("output", {})
                
            return False, None
            
        except Exception as e:
            self.logger.error(f"응답 처리 중 오류: {str(e)}")
            return False, None
            
    async def _subscribe_hts(self) -> bool:
        """HTS ID 구독"""
        try:
            if not await self.ensure_connection():
                return False

            tr_id = 'H0STCNI0' if self.account_info.is_live else 'H0STCNI9'
            subscribe_data = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": tr_id,
                        "tr_key": self.account_info.hts_id
                    }
                }
            }
            
            # 구독 요청 전송
            self.websocket.send(json.dumps(subscribe_data))
            
            # 응답 수신 및 처리
            response = self.websocket.recv()
            success, _ = self._process_response(response)
            
            if success:
                self.logger.info("✅ HTS ID 구독 성공")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"⚠ HTS ID 구독 중 오류: {str(e)}")
            self._closed = True
            return False
            
    async def check_connection(self) -> bool:
        """연결 상태 확인"""
        return await self.ensure_connection()
            
    async def disconnect(self) -> None:
        """웹소켓 연결 종료 (호환성을 위한 메서드)"""
        await self.close()
            
    async def close(self) -> None:
        """웹소켓 연결 종료"""
        if not self._closed:
            self._closed = True
            if self.websocket:
                try:
                    self.websocket.close()
                    self.logger.info("✅ 웹소켓 연결 종료")
                except Exception as e:
                    self.logger.error(f"⚠ 웹소켓 종료 중 오류: {str(e)}")
                finally:
                    self.websocket = None

    async def subscribe_vi_stock(self) -> bool:
        """VI 데이터 구독
        
        Returns:
            bool: 구독 성공 여부
        """
        try:
            if not await self.ensure_connection():
                return False
                
            # VI 데이터 구독 메시지 생성
            subscribe_message = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",  # VI 발동 실시간 조회 TR
                        "tr_key": "0001"
                    }
                }
            }
            
            # 구독 메시지 전송
            self.websocket.send(json.dumps(subscribe_message))
            
            # 응답 수신 및 처리
            response = self.websocket.recv()
            success, _ = self._process_response(response)
            
            if success:
                self.logger.info("VI 데이터 구독 요청이 전송되었습니다.")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"VI 데이터 구독 중 오류 발생: {str(e)}")
            self._closed = True
            return False

    async def receive_vi_stock(self) -> dict:
        """데이터 수신
        
        Returns:
            dict: 수신된 데이터
        """
        try:
            if not await self.ensure_connection():
                return {}
                
            # 데이터 수신
            message = self.websocket.recv()
            success, data = self._process_response(message)
            
            if success and data:
                return data
                
            return {}
            
        except Exception as e:
            self.logger.error(f"데이터 수신 중 오류 발생: {str(e)}")
            self._closed = True
            return {}

    async def subscribe_stock_ccld(self, stock: str) -> bool:
        """주식 체결 정보 구독
        
        Args:
            stock: 종목 코드
            
        Returns:
            bool: 구독 성공 여부
        """
        try:
            if not await self.ensure_connection():
                return False
                
            # 체결 정보 구독 메시지 생성
            subscribe_message = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STASP0",  # 실시간 체결 정보 TR
                        "tr_key": stock     # 종목 코드
                    }
                }
            }
            
            # 구독 메시지 전송
            self.websocket.send(json.dumps(subscribe_message))
            
            # 응답 수신 및 처리
            response = self.websocket.recv()
            success, _ = self._process_response(response)
            
            if success:
                self.logger.info(f"✅ 종목 체결 정보 구독 요청 전송 (종목: {stock})")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"⚠ 종목 체결 정보 구독 중 오류: {str(e)}")
            self._closed = True
            return False

    async def receive_stock_ccld(self) -> dict:
        """종목 체결 정보 수신
        
        Returns:
            dict: 수신된 체결 정보
        """
        try:
            if not await self.ensure_connection():
                return {}
                
            # 데이터 수신
            message = self.websocket.recv()
            success, data = self._process_response(message)
            
            if success and data:
                return data
                
            return {}
            
        except Exception as e:
            self.logger.error(f"⚠ 종목 체결 정보 수신 중 오류: {str(e)}")
            self._closed = True
            return {}

    async def unsubscribe_vi_stock(self) -> bool:
        """VI 데이터 구독 취소
        
        Returns:
            bool: 구독 취소 성공 여부
        """
        try:
            if not await self.ensure_connection():
                return False
                
            # 구독 취소 메시지 생성
            unsubscribe_message = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "2",  # 구독 취소
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",  # VI 발동 실시간 조회 TR
                        "tr_key": "0001"
                    }
                }
            }
            
            # 구독 취소 메시지 전송
            self.websocket.send(json.dumps(unsubscribe_message))
            
            # 응답 수신 및 처리
            response = self.websocket.recv()
            success, _ = self._process_response(response)
            
            if success:
                self.logger.info("✅ VI 데이터 구독 취소 요청 전송")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"⚠ VI 데이터 구독 취소 중 오류: {str(e)}")
            self._closed = True
            return False

    async def unsubscribe_stock_ccld(self, stock: str) -> bool:
        """종목 체결 정보 구독 취소
        
        Args:
            stock: 종목 코드
            
        Returns:
            bool: 구독 취소 성공 여부
        """
        try:
            if not await self.ensure_connection():
                return False
                
            # 구독 취소 메시지 생성
            unsubscribe_message = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "2",  # 구독 취소
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STASP0",  # 실시간 체결 정보 TR
                        "tr_key": stock     # 종목 코드
                    }
                }
            }
            
            # 구독 취소 메시지 전송
            self.websocket.send(json.dumps(unsubscribe_message))
            
            # 응답 수신 및 처리
            response = self.websocket.recv()
            success, _ = self._process_response(response)
            
            if success:
                self.logger.info(f"✅ 종목 체결 정보 구독 취소 요청 전송 (종목: {stock})")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"⚠ 종목 체결 정보 구독 취소 중 오류: {str(e)}")
            self._closed = True
            return False 