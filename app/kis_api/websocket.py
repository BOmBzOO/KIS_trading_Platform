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
        self._ping_interval = 60  # ping 간격을 20초로 설정
        self._last_ping = datetime.now().timestamp()
        self._ping_timeout = 60  # ping 타임아웃 10초
        self._is_subscribed = False  # 구독 상태 추적
            
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
            
            # 웹소켓 연결 설정
            self.websocket.settimeout(30)  # 초기 연결 타임아웃 설정
            self.websocket.connect(
                ws_url, 
                ping_interval=self._ping_interval, 
                ping_timeout=self._ping_timeout
                )
            self.websocket.settimeout(None)  # 타임아웃 해제
            
            self.logger.info(f"✅ 웹소켓 연결 성공")
            
            # HTS ID 구독
            if await self._subscribe_hts():
                self._reconnect_attempts = 0  # 연결 성공 시 재연결 시도 횟수 초기화
                self._closed = False
                self._is_subscribed = True
                return True
            else:
                self._closed = True
                return False
            
        except Exception as e:
            self.logger.error(f"⚠ 웹소켓 연결 실패: {str(e)}")
            if self.websocket:
                self.websocket.close()
                self.websocket = None
            self._closed = True
            self._is_subscribed = False
            return False
        finally:
            self._is_connecting = False

    async def ensure_connection(self) -> bool:
        """웹소켓 연결 상태 확인 및 필요시 재연결"""
        if not self.websocket or self._closed:
            if self._reconnect_attempts < self._max_reconnect_attempts:
                self._reconnect_attempts += 1
                self.logger.info(f"웹소켓 재연결 시도 {self._reconnect_attempts}/{self._max_reconnect_attempts}")
                await asyncio.sleep(self._reconnect_delay)
                return await self.connect()
            else:
                self.logger.error("최대 재연결 시도 횟수 초과")
                return False

        current_time = datetime.now().timestamp()
        
        # ping 간격 체크
        if current_time - self._last_ping >= self._ping_interval:
            try:
                self.websocket.ping()
                self._last_ping = current_time
            except Exception as e:
                self.logger.error(f"ping 전송 실패: {str(e)}")
                self._closed = True
                self._is_subscribed = False
                return await self.ensure_connection()

        # pong 타임아웃 체크
        if current_time - self._last_pong >= self._ping_timeout:
            self.logger.error("ping 응답 타임아웃")
            self._closed = True
            self._is_subscribed = False
            return await self.ensure_connection()

        return True

    def _process_response(self, data: str) -> Tuple[bool, Optional[dict]]:
        """응답 데이터 처리
        
        Args:
            data: 수신된 데이터
            
        Returns:
            Tuple[bool, Optional[dict]]: (성공 여부, 처리된 데이터)
        """
        try:
            # PINGPONG 처리
            if data.startswith('{"header":{"tr_id":"PINGPONG"'):
                self.logger.info(f"PINGPONG 응답 수신: {data}")
                self._last_pong = datetime.now().timestamp()
                return True, None
                
            # 실시간 데이터인 경우
            if data[0] in ['0', '1']:
                self.logger.debug(f"실시간 데이터 수신: {data}")
                return True, None
                
            # JSON 응답인 경우
            json_data = json.loads(data)
            tr_id = json_data.get("header", {}).get("tr_id")
            
            # VI 데이터 처리
            if tr_id == "H0STCNT0":
                output = json_data.get("body", {}).get("output", {})
                vi_type = output.get("vi_type", "")
                vi_type_map = {
                    "1": "VI 발동",
                    "2": "VI 해제",
                    "3": "VI 발동 예정",
                    "4": "VI 해제 예정"
                }
                vi_status = vi_type_map.get(vi_type, "알 수 없음")
                self.logger.info(f"VI 상태 변경: {vi_status} (종목: {output.get('stock')}, 가격: {output.get('vi_price')})")
                return True, output
            
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
                    self.logger.info(f"✅ HTS ID 구독 성공 (TRID [{tr_id}] KEY[{self._aes_key}] IV[{self._aes_iv}])")
                    
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
                # self.logger.info("✅ HTS ID 구독 성공")
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
            self._is_subscribed = False
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
            self._is_subscribed = False
            return False

    async def receive_vi_stock(self) -> dict:
        """데이터 수신
        
        Returns:
            dict: 수신된 데이터
        """
        try:
            if not await self.ensure_connection():
                return {}
                
            # 데이터 수신 타임아웃 설정
            self.websocket.settimeout(10)  # 타임아웃을 10초로 증가
            message = self.websocket.recv()
            self.websocket.settimeout(None)  # 타임아웃 해제

            # 메시지 로깅 추가
            self.logger.debug(f"수신된 메시지: {message}")

            success, data = self._process_response(message)
            
            if success and data:
                # 데이터 구조 검증
                if not isinstance(data, dict):
                    self.logger.error(f"잘못된 데이터 형식: {type(data)}")
                    return {}
                    
                # VI 데이터 필드 검증
                required_fields = ["stock", "vi_type", "vi_price", "vi_time"]
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    self.logger.error(f"필수 필드 누락: {missing_fields}")
                    return {}
                    
                return data
                
            return {}
            
        except websocket.WebSocketTimeoutException:
            self.logger.debug("데이터 수신 타임아웃")
            return {}
        except Exception as e:
            self.logger.error(f"데이터 수신 중 오류 발생: {str(e)}")
            return {}

    async def subscribe_stock_ccld(self, data: str) -> bool:
        """주식 체결 정보 구독
        
        Args:
            data: receive_vi_stock을 통해 받은 데이터
            
        Returns:
            bool: 구독 성공 여부
        """
        try:
            if not await self.ensure_connection():
                return False
            
            # 데이터 구조 검증
            if not data:
                self.logger.error("빈 데이터가 전달되었습니다.")
                return False
                
            # 데이터가 이미 딕셔너리인 경우 처리
            if isinstance(data, dict):
                stock = data.get("stock", "")
            else:
                # 문자열인 경우 JSON 파싱
                try:
                    data = json.loads(data)
                    stock = data.get("stock", "")
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 파싱 오류: {str(e)}")
                    return False
            
            if not stock:
                self.logger.error(f"종목 코드를 찾을 수 없습니다. 데이터: {data}")
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