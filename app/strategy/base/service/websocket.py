"""KIS 웹소켓 클라이언트"""

import asyncio
import json
import logging
from typing import Optional
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
        
        # approval_key 업데이트
        self._update_approval_key()
        
    def _update_approval_key(self) -> None:
        """approval_key 발급"""
        try:
            self.account_info.approval_key = get_approval_key(
                app_key=self.account_info.app_key,
                app_secret=self.account_info.app_secret,
                is_live=self.account_info.is_live
            )
            save_account_info_to_env(
                approval_key=self.account_info.approval_key,
                kis_access_token=self.account_info.kis_access_token,
                access_token_expired=self.account_info.access_token_expired,
                hts_id=self.account_info.hts_id,
                app_key=self.account_info.app_key,
                app_secret=self.account_info.app_secret,
                is_live=self.account_info.is_live,
                cano=self.account_info.cano,
                acnt_prdt_cd=self.account_info.acnt_prdt_cd,
                acnt_type=self.account_info.acnt_type,
                acnt_name=self.account_info.acnt_name,
                owner_name=self.account_info.owner_name,
                owner_id=self.account_info.owner_id,
                id=self.account_info.id,
                discord_webhook_url=self.account_info.discord_webhook_url,
            )
            self.logger.info("✅ Approval key 발급 완료")
        except Exception as e:
            self.logger.error(f"⚠ Approval key 발급 실패: {str(e)}")
            raise
            
    async def connect(self) -> bool:
        """웹소켓 연결 수립"""
        try:
            if self.websocket:
                await self.close()
                
            self.websocket = websocket.WebSocket()
            ws_url = APIConfig.KIS_WEBSOCKET_URL if self.account_info.is_live else APIConfig.KIS_WEBSOCKET_URL_PAPER
            
            # 웹소켓 연결
            self.websocket.connect(ws_url, ping_interval=60)
            self.logger.info(f"✅ 웹소켓 연결 성공 ({'실전' if self.account_info.is_live else '모의'})")
            
            # HTS ID 구독
            await self._subscribe_hts()
            return True
            
        except Exception as e:
            self.logger.error(f"⚠ 웹소켓 연결 실패: {str(e)}")
            if self.websocket:
                self.websocket.close()
                self.websocket = None
            return False
            
    async def _subscribe_hts(self) -> bool:
        """HTS ID 구독"""
        try:
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
            
            self.websocket.send(json.dumps(subscribe_data))
            response = self.websocket.recv()
            
            if response[0] in ['0', '1']:
                self.logger.info("✅ HTS ID 구독 성공")
                return True
                
            self.logger.error("⚠ HTS ID 구독 실패")
            return False
            
        except Exception as e:
            self.logger.error(f"⚠ HTS ID 구독 중 오류: {str(e)}")
            return False
            
    async def check_connection(self) -> bool:
        """연결 상태 확인"""
        if not self.websocket:
            return False
            
        try:
            if datetime.now().timestamp() - self._last_pong > 30:
                self.websocket.ping()
                self._last_pong = datetime.now().timestamp()
            return True
        except Exception:
            return False
            
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

