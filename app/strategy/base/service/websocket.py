"""KIS 웹소켓 클라이언트"""

import asyncio
import json
import logging
import signal
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
import websocket
import time
from app.auth.models import AccountInfo
from app.auth.service import get_approval_key
from app.common.constants import APIConfig
from app.common.utils import save_account_info_to_env


class KISWebSocketClient:
    """KIS WebSocket 기본 클라이언트"""

    def __init__(self, account_info: AccountInfo):
        self.account_info = account_info
        self.websocket = None
        self._closed = False
        self.logger = logging.getLogger("KISWebSocket")
        self._last_pong = datetime.now().timestamp()
        self.aes_key = None
        self.aes_iv = None
        self._shutdown_event = asyncio.Event()
        
        self._save_account_info()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._signal_handler(s)))
            self.logger.info("시그널 핸들러가 등록되었습니다.")
        except NotImplementedError:
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self._sync_signal_handler)
            self.logger.info("Windows 시그널 핸들러가 등록되었습니다.")
            
    def _sync_signal_handler(self, sig, frame):
        """동기 시그널 처리 (Windows용)"""
        self.logger.info(f"시그널 수신: {sig}")
        loop = asyncio.get_event_loop()
        loop.create_task(self.shutdown())
        loop.call_soon_threadsafe(loop.stop)
            
    async def _signal_handler(self, sig):
        """비동기 시그널 처리"""
        self.logger.info(f"시그널 수신: {sig.name}")
        await self.shutdown()
        loop = asyncio.get_running_loop()
        loop.stop()
        
    async def shutdown(self):
        """안전한 종료 처리"""
        if not self._closed:
            self.logger.info("안전한 종료를 시작합니다...")
            self._closed = True
            self._shutdown_event.set()
            
            if self.websocket:
                try:
                    self.websocket.close()
                    self.logger.info("웹소켓 연결이 종료되었습니다.")
                except Exception as e:
                    self.logger.error(f"웹소켓 종료 중 오류 발생: {str(e)}")
                finally:
                    self.websocket = None
            
            self._save_account_info()
            self.logger.info("현재 상태가 저장되었습니다.")
            
            await asyncio.sleep(1)
            self.logger.info("프로그램을 종료합니다.")

    def _save_account_info(self) -> None:
        """계정 정보를 .env 파일에 저장"""
        try:
            save_account_info_to_env(
                kis_access_token=self.account_info.kis_access_token,
                access_token_expired=self.account_info.access_token_expired,
                approval_key=self.account_info.approval_key,
                hts_id=self.account_info.hts_id,
                app_key=self.account_info.app_key,
                app_secret=self.account_info.app_secret,
                is_live=self.account_info.is_live,
                cano=self.account_info.cano,
                acnt_prdt_cd=getattr(self.account_info, 'acnt_prdt_cd', "01"),
                acnt_type=getattr(self.account_info, 'acnt_type', "live"),
                acnt_name=getattr(self.account_info, 'acnt_name', ""),
                discord_webhook_url=self.account_info.discord_webhook_url,
                owner_name=getattr(self.account_info, 'owner_name', ""),
                owner_id=getattr(self.account_info, 'owner_id', ""),
                id=getattr(self.account_info, 'id', "")
            )
            self.logger.info("계정 정보가 .env 파일에 저장되었습니다.")
        except Exception as e:
            self.logger.error(f"계정 정보 저장 중 오류 발생: {str(e)}")

    def update_account_info(self, account_info: AccountInfo) -> None:
        """계정 정보 업데이트 및 .env 파일 갱신"""
        self.account_info = account_info
        self._save_account_info()

    def _is_token_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        now = datetime.now()
        return now >= self.account_info.access_token_expired

    async def _check_connection(self) -> bool:
        """연결 상태 확인"""
        if not self.websocket:
            return False
            
        try:
            if datetime.now().timestamp() - self._last_pong > 30:
                self.websocket.ping()
                self.logger.debug("PING 전송")
            return True
        except Exception as e:
            self.logger.error(f"연결 상태 확인 중 오류: {str(e)}")
            return False

    async def _connection_monitor(self):
        """연결 상태 모니터링"""
        while not self._closed:
            try:
                if self._shutdown_event.is_set():
                    break

                if not await self._check_connection():
                    self.logger.warning("연결이 끊어졌습니다. 재연결을 시도합니다.")
                    if await self.connect():
                        self.logger.info("재연결 성공")
                    else:
                        self.logger.error("재연결 실패")
                else:
                    self.logger.debug("연결 상태 양호")

                await asyncio.sleep(10)

            except Exception as e:
                self.logger.error(f"연결 모니터링 중 오류: {str(e)}")
                await asyncio.sleep(5)

    async def connect(self) -> bool:
        """웹소켓 연결"""
        try:
            if self._is_token_expired():
                self.logger.error(f"토큰이 만료되었습니다. (만료시간: {self.account_info.access_token_expired})")
                return False

            if not self.account_info.approval_key:
                try:
                    self.account_info.approval_key = get_approval_key(
                        app_key=self.account_info.app_key,
                        app_secret=self.account_info.app_secret,
                        is_live=self.account_info.is_live
                    )
                    self.logger.info("Approval key 발급 완료")
                    self._save_account_info()
                except Exception as e:
                    self.logger.error(f"Approval key 발급 실패: {str(e)}", exc_info=True)
                    return False

            if self.websocket:
                try:
                    self.websocket.close()
                except Exception as e:
                    self.logger.error(f"기존 웹소켓 종료 중 오류: {str(e)}", exc_info=True)
                self.websocket = None
                await asyncio.sleep(1)

            self.websocket = websocket.WebSocket()
            ws_url = APIConfig.KIS_WEBSOCKET_URL if self.account_info.is_live else APIConfig.KIS_WEBSOCKET_URL_PAPER
            self.logger.info(f"웹소켓 연결 시도: {ws_url}")
            
            try:
                self.websocket.connect(ws_url, ping_interval=60)
                self.logger.info(f"웹소켓 연결 성공 ({'실전' if self.account_info.is_live else '모의'})")
            except Exception as e:
                self.logger.error(f"웹소켓 연결 실패: {str(e)}", exc_info=True)
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
            
            try:
                self.websocket.send(json.dumps(subscribe_data))
                response = self.websocket.recv()
                
                if response[0] in ['0', '1']:
                    pass
                else:
                    response_data = json.loads(response)
                    if "header" in response_data:
                        tr_id_resp = response_data["header"].get("tr_id")
                        if tr_id_resp in ["H0STCNI0", "H0STCNI9"]:
                            output = response_data.get("body", {}).get("output", {})
                            if output:
                                self.aes_key = output.get("key", "")
                                self.aes_iv = output.get("iv", "")
                                self.logger.info(f"AES 키/IV 수신 완료: {tr_id_resp}")
                            else:
                                self.logger.error("AES 키/IV 수신 실패")
                                return False
                
                self._last_pong = datetime.now().timestamp()
                asyncio.create_task(self._connection_monitor())
                self.logger.info("연결 모니터링이 시작되었습니다.")
                return True
                
            except Exception as e:
                self.logger.error(f"초기 구독 설정 중 오류 발생: {str(e)}", exc_info=True)
                if self.websocket:
                    try:
                        self.websocket.close()
                    except Exception:
                        pass
                    self.websocket = None
                return False

        except Exception as e:
            self.logger.error(f"웹소켓 연결 오류: {str(e)}", exc_info=True)
            if self.websocket:
                try:
                    self.websocket.close()
                except Exception:
                    pass
                self.websocket = None
            return False

    async def subscribe(self, tr_id: str, tr_key: str = "") -> bool:
        """TR 구독"""
        if not self.websocket or self._is_token_expired():
            self.logger.warning("웹소켓이 없거나 토큰이 만료됨")
            return False

        try:
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
                        "tr_key": tr_key
                    }
                }
            }
            
            self.websocket.send(json.dumps(subscribe_data))
            self.logger.info(f"TR 구독 요청: {tr_id}")
            
            response = self.websocket.recv()
            
            if response == "PINGPONG":
                self._last_pong = datetime.now().timestamp()
                return True
                
            response_data = json.loads(response)
            if "header" in response_data:
                rt_cd = response_data.get("body", {}).get("rt_cd")
                if rt_cd == '1':
                    self.logger.error(f"TR 구독 실패: {response_data.get('body', {}).get('msg1')}")
                    return False
                self.logger.info(f"TR 구독 성공: {tr_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"TR 구독 요청 중 오류 발생: {str(e)}")
            return False

    async def disconnect(self) -> None:
        """웹소켓 연결 종료"""
        await self.close()

    async def close(self):
        """웹소켓 종료"""
        await self.shutdown()

