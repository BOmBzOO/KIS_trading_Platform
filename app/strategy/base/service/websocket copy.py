"""VI 웹소켓 클라이언트"""

import asyncio
import json
import logging
import signal
from typing import Optional, AsyncGenerator, Dict, Any, Callable
from datetime import datetime, timezone, timedelta
import websocket  # websocket-client 라이브러리 사용
import time
from app.auth.models import AccountInfo
from app.auth.service import get_approval_key
from app.common.constants import APIConfig, WebSocketConfig, VIConfig
from app.common.utils import save_account_info_to_env
import websocket
from websockets.client import WebSocketClientProtocol


class KISWebSocketClient:
    """KIS WebSocket을 이용한 VI 모니터링"""

    def __init__(self, account_info: AccountInfo):
        self.account_info = account_info  # 사용자 계정 정보 저장
        self.websocket = None
        self._closed = False
        self.logger = logging.getLogger("KISWebSocket")
        self.vi_triggered_stocks: Dict[str, float] = {}  # 종목코드: VI 발동 시간
        self._last_pong = datetime.now().timestamp()  # 마지막 PONG 시간
        self.aes_key = None  # AES 암호화 키
        self.aes_iv = None   # AES 초기화 벡터
        self._shutdown_event = asyncio.Event()  # 종료 이벤트
        
        # 초기 계정 정보를 .env에 저장
        self._save_account_info()
        
        # 시그널 핸들러 등록
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._signal_handler(s)))
            self.logger.info("✅ 시그널 핸들러가 등록되었습니다.")
        except NotImplementedError:
            # Windows에서는 add_signal_handler가 지원되지 않음
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self._sync_signal_handler)
            self.logger.info("✅ Windows 시그널 핸들러가 등록되었습니다.")
            
    def _sync_signal_handler(self, sig, frame):
        """동기 시그널 처리 (Windows용)"""
        self.logger.info(f"🛑 시그널 수신: {sig}")
        loop = asyncio.get_event_loop()
        loop.create_task(self.shutdown())
        # Windows에서는 메인 스레드에서 이벤트 루프를 중지
        loop.call_soon_threadsafe(loop.stop)
            
    async def _signal_handler(self, sig):
        """비동기 시그널 처리"""
        self.logger.info(f"🛑 시그널 수신: {sig.name}")
        await self.shutdown()
        # 이벤트 루프 중지
        loop = asyncio.get_running_loop()
        loop.stop()
        
    async def shutdown(self):
        """안전한 종료 처리"""
        if not self._closed:
            self.logger.info("🔄 안전한 종료를 시작합니다...")
            self._closed = True
            self._shutdown_event.set()
            
            # 웹소켓 연결 종료
            if self.websocket:
                try:
                    self.websocket.close()
                    self.logger.info("✅ 웹소켓 연결이 종료되었습니다.")
                except Exception as e:
                    self.logger.error(f"⚠ 웹소켓 종료 중 오류 발생: {str(e)}")
                finally:
                    self.websocket = None
            
            # 현재 상태 저장
            self._save_account_info()
            self.logger.info("✅ 현재 상태가 저장되었습니다.")
            
            # 잠시 대기 후 종료
            await asyncio.sleep(1)
            self.logger.info("👋 프로그램을 종료합니다.")

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
            self.logger.info("✅ 계정 정보가 .env 파일에 저장되었습니다.")
        except Exception as e:
            self.logger.error(f"⚠ 계정 정보 저장 중 오류 발생: {str(e)}")

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
            # 마지막 PONG으로부터 30초 이상 경과
            if datetime.now().timestamp() - self._last_pong > 30:
                self.websocket.ping()
                self.logger.debug("🔄 PING 전송")
            return True
        except Exception as e:
            self.logger.error(f"⚠ 연결 상태 확인 중 오류: {str(e)}")
            return False

    async def _connection_monitor(self):
        """연결 상태 모니터링"""
        while not self._closed:
            try:
                # 종료 이벤트 확인
                if self._shutdown_event.is_set():
                    break

                # 연결 상태 확인
                if not await self._check_connection():
                    self.logger.warning("⚠ 연결이 끊어졌습니다. 재연결을 시도합니다.")
                    if await self.connect():
                        self.logger.info("✅ 재연결 성공")
                    else:
                        self.logger.error("❌ 재연결 실패")
                else:
                    self.logger.debug("✅ 연결 상태 양호")

                await asyncio.sleep(10)  # 10초마다 확인

            except Exception as e:
                self.logger.error(f"⚠ 연결 모니터링 중 오류: {str(e)}")
                await asyncio.sleep(5)

    async def connect(self) -> bool:
        """웹소켓 연결"""
        try:
            if self._is_token_expired():
                self.logger.error(f"❌ 토큰이 만료되었습니다. (만료시간: {self.account_info.access_token_expired})")
                return False

            # approval_key가 없거나 갱신이 필요한 경우
            if not self.account_info.approval_key:
                try:
                    self.account_info.approval_key = get_approval_key(
                        app_key=self.account_info.app_key,
                        app_secret=self.account_info.app_secret,
                        is_live=self.account_info.is_live
                    )
                    self.logger.info("✅ Approval key 발급 완료")
                    self._save_account_info()
                except Exception as e:
                    self.logger.error(f"⚠ Approval key 발급 실패: {str(e)}", exc_info=True)
                    return False

            # 기존 연결 종료
            if self.websocket:
                try:
                    self.websocket.close()
                except Exception as e:
                    self.logger.error(f"⚠ 기존 웹소켓 종료 중 오류: {str(e)}", exc_info=True)
                self.websocket = None
                await asyncio.sleep(1)  # 연결 종료 후 잠시 대기

            # websocket-client를 사용한 연결
            self.websocket = websocket.WebSocket()
            ws_url = APIConfig.KIS_WEBSOCKET_URL if self.account_info.is_live else APIConfig.KIS_WEBSOCKET_URL_PAPER
            self.logger.info(f"🔄 웹소켓 연결 시도: {ws_url}")
            
            try:
                self.websocket.connect(ws_url, ping_interval=60)
                self.logger.info(f"✅ 웹소켓 연결 성공 ({'실전' if self.account_info.is_live else '모의'})")
            except Exception as e:
                self.logger.error(f"⚠ 웹소켓 연결 실패: {str(e)}", exc_info=True)
                return False

            # HTS ID 구독 설정
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
                                self.logger.info(f"✅ AES 키/IV 수신 완료: {tr_id_resp}")
                            else:
                                self.logger.error("⚠ AES 키/IV 수신 실패")
                                return False
                
                self._last_pong = datetime.now().timestamp()
                asyncio.create_task(self._connection_monitor())
                self.logger.info("✅ 연결 모니터링이 시작되었습니다.")
                return True
                
            except Exception as e:
                self.logger.error(f"⚠ 초기 구독 설정 중 오류 발생: {str(e)}", exc_info=True)
                if self.websocket:
                    try:
                        self.websocket.close()
                    except Exception:
                        pass
                    self.websocket = None
                return False

        except Exception as e:
            self.logger.error(f"⚠ 웹소켓 연결 오류: {str(e)}", exc_info=True)
            if self.websocket:
                try:
                    self.websocket.close()
                except Exception:
                    pass
                self.websocket = None
            return False

    async def _ping_monitor(self):
        """ping/pong 모니터링"""
        while not self._closed:
            try:
                if self.websocket:
                    await self.websocket.ping()
                    self._last_pong = datetime.now().timestamp()
                await asyncio.sleep(10)  # 10초마다 ping 전송
            except Exception:
                self.logger.warning("⚠ ping/pong 실패")
                break

    async def disconnect(self) -> None:
        """웹소켓 연결 종료"""
        await self.close()

    async def close(self):
        """웹소켓 종료"""
        await self.shutdown()

    async def _subscribe_vi(self):
        """VI 발동 정보 구독"""
        if not self.websocket or self._is_token_expired():
            self.logger.warning("❌ 웹소켓이 없거나 토큰이 만료됨. 구독 요청 취소")
            return False

        try:
            # 구독할 TR 목록 생성
            subscribe_list = [
                ['1', 'H0STCNI0', self.account_info.hts_id],  # HTS ID 구독 (실시간 시세 암호화키)
                ['1', VIConfig.REALTIME_TR, '']  # VI 발동 구독
            ]
            
            # 각 TR 구독 요청
            for tr_type, tr_id, tr_key in subscribe_list:
                subscribe_data = {
                    "header": {
                        "approval_key": self.account_info.approval_key,
                        "custtype": "P",
                        "tr_type": tr_type,
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
                self.logger.info(f"📡 TR 구독 요청 완료: {tr_id}")
                
                # 응답 대기 및 처리
                try:
                    response = self.websocket.recv()
                    
                    if response == "PINGPONG":
                        self._last_pong = datetime.now().timestamp()
                        continue
                        
                    response_data = json.loads(response)
                    if "header" in response_data:
                        tr_id_resp = response_data["header"].get("tr_id")
                        
                        # HTS ID 구독 응답 처리
                        if tr_id_resp in ["H0STCNI0", "H0STCNI9"]:
                            output = response_data.get("body", {}).get("output", {})
                            if output:
                                self.aes_key = output.get("key", "")
                                self.aes_iv = output.get("iv", "")
                                self.logger.info(f"✅ AES 키/IV 수신 완료: {tr_id_resp}")
                            else:
                                self.logger.error("⚠ AES 키/IV 수신 실패")
                                return False
                        else:
                            rt_cd = response_data.get("body", {}).get("rt_cd")
                            if rt_cd == '1':
                                self.logger.error(f"⚠ TR 구독 실패: {tr_id}, {response_data.get('body', {}).get('msg1')}")
                                return False
                            self.logger.info(f"✅ TR 구독 성공: {tr_id}")
                            
                except Exception as e:
                    self.logger.error(f"⚠ TR 구독 응답 처리 중 오류: {str(e)}")
                    return False
                    
                time.sleep(0.2)  # 요청 간 딜레이
                
            return True
                
        except Exception as e:
            self.logger.error(f"⚠ 구독 요청 중 오류 발생: {str(e)}")
            return False

    async def _subscribe_realtime_trade(self, stock_code: str):
        """VI 종목의 실시간 체결 정보 구독"""
        if not self.websocket or self._is_token_expired():
            self.logger.warning("❌ 웹소켓이 없거나 토큰이 만료됨. 체결 정보 구독 요청 취소")
            return False

        try:
            subscribe_data = {
                "header": {
                    "approval_key": self.account_info.approval_key,
                    "custtype": "P",
                    "tr_type": "1",  # 구독 요청
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": VIConfig.TRADE_TR,
                        "tr_key": stock_code
                    }
                }
            }
            
            self.websocket.send(json.dumps(subscribe_data))
            self.logger.info(f"📡 실시간 체결 정보 구독 요청: {stock_code}")
            
            # 응답 대기 및 처리
            try:
                response = self.websocket.recv()
                
                if response == "PINGPONG":
                    self._last_pong = datetime.now().timestamp()
                    return True
                    
                response_data = json.loads(response)
                if "header" in response_data:
                    rt_cd = response_data.get("body", {}).get("rt_cd")
                    if rt_cd == '1':
                        self.logger.error(f"⚠ 체결 정보 구독 실패: {response_data.get('body', {}).get('msg1')}")
                        return False
                    self.logger.info(f"✅ 체결 정보 구독 성공: {stock_code}")
                    return True
                    
            except Exception as e:
                self.logger.error(f"⚠ 체결 정보 구독 응답 처리 중 오류: {str(e)}")
                return False
                
            time.sleep(0.2)  # 요청 간 딜레이
            return True
                
        except Exception as e:
            self.logger.error(f"⚠ 체결 정보 구독 요청 중 오류 발생: {str(e)}")
            return False

    async def subscribe_vi_data(self) -> AsyncGenerator[dict, None]:
        """VI 발동 및 해제 데이터 수신"""
        retry_count = 0
        last_reconnect = 0

        while not self._closed:
            try:
                # 종료 이벤트 확인
                if self._shutdown_event.is_set():
                    self.logger.info("🛑 종료 요청이 감지되었습니다.")
                    break
                    
                # 연결 상태 확인
                if not self.websocket:
                    current_time = datetime.now().timestamp()
                    
                    # 재연결 시도 간격 제한 (최소 5초)
                    if current_time - last_reconnect < 5:
                        await asyncio.sleep(1)
                        continue
                        
                    if retry_count >= WebSocketConfig.MAX_RETRY_COUNT:
                        self.logger.error("⚠ 최대 재연결 횟수 초과.")
                        break

                    self.logger.warning("🔄 웹소켓 재연결 시도 중...")
                    if await self.connect():
                        retry_count = 0
                    else:
                        retry_count += 1
                        last_reconnect = current_time
                        await asyncio.sleep(WebSocketConfig.RETRY_DELAY)
                    continue

                try:
                    message = self.websocket.recv()
                except websocket.WebSocketConnectionClosedException:
                    if not self._closed:  # 정상적인 종료가 아닌 경우에만 경고
                        self.logger.warning("⚠ 웹소켓 연결이 종료됨")
                    self.websocket = None
                    continue
                except Exception as e:
                    if not self._closed:  # 정상적인 종료가 아닌 경우에만 에러 로깅
                        self.logger.error(f"⚠ 메시지 수신 중 오류: {str(e)}")
                    await asyncio.sleep(1)
                    continue

                self.logger.debug(f"📩 수신된 메시지: {message}")

                if message == "PINGPONG":
                    self.logger.debug("🔄 [PINGPONG] 수신됨")
                    self._last_pong = datetime.now().timestamp()
                    continue

                # 실시간 데이터 처리
                if message[0] in ['0', '1']:
                    recvstr = message.split('|')
                    if len(recvstr) < 4:  # 메시지 형식 검증
                        self.logger.warning(f"⚠ 잘못된 메시지 형식: {message}")
                        continue
                        
                    tr_id = recvstr[1]
                    data = None

                    if tr_id == VIConfig.REALTIME_TR:  # VI 발동
                        try:
                            data = self._parse_vi_data(recvstr[3])
                            stock_code = data["stck_shrn_iscd"]
                            self.logger.info(f"⚡ VI 발동 감지: {stock_code}")
                            self.vi_triggered_stocks[stock_code] = datetime.now().timestamp()
                            await self._subscribe_realtime_trade(stock_code)
                        except Exception as e:
                            self.logger.error(f"⚠ VI 데이터 파싱 오류: {str(e)}")

                    elif tr_id == "H0STASP0":  # 실시간 체결
                        try:
                            data = self._parse_trade_data(recvstr[3])
                            stock_code = data["stck_shrn_iscd"]
                            if stock_code in self.vi_triggered_stocks:
                                elapsed_time = datetime.now().timestamp() - self.vi_triggered_stocks[stock_code]
                                if elapsed_time > 120:  # 2분 경과
                                    self.logger.info(f"✅ VI 해제 감지: {stock_code}")
                                    del self.vi_triggered_stocks[stock_code]
                        except Exception as e:
                            self.logger.error(f"⚠ 체결 데이터 파싱 오류: {str(e)}")

                    if data:
                        yield data

            except asyncio.CancelledError:
                self.logger.info("✅ 웹소켓 수신 작업이 취소됨")
                break
            except Exception as e:
                if not self._closed:  # 정상적인 종료가 아닌 경우에만 에러 로깅
                    self.logger.error(f"⚠ 메시지 처리 중 오류 발생: {str(e)}")
                await asyncio.sleep(1)

        # 종료 전 정리
        await self.shutdown()
        self.logger.info("✅ VI 데이터 구독이 종료되었습니다.")

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


class WebSocketClient:
    """웹소켓 클라이언트
    
    VI 데이터를 실시간으로 수신하기 위한 웹소켓 클라이언트입니다.
    """
    
    def __init__(
        self,
        account_info: AccountInfo,
        base_url: str,
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Args:
            account_info: 계좌 정보
            on_message: 메시지 수신 시 호출할 콜백 함수
            base_url: 웹소켓 서버 URL (기본값: APIConfig.EXTERNAL_WS_URL)
        """
        self.account_info = account_info
        self.base_url = APIConfig.KIS_BASE_URL_LIVE if self.account_info.is_live else APIConfig.KIS_BASE_URL_PAPER
        self.websocket_url = APIConfig.KIS_WEBSOCKET_URL if self.account_info.is_live else APIConfig.KIS_WEBSOCKET_URL_PAPER
        self.on_message = on_message
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
    def _is_token_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        now = datetime.now(tz=timezone.kst)
        return now >= self.account_info.access_token_expired
        
    async def connect(self) -> None:
        """웹소켓 연결
        
        1. 토큰이 만료되었는지 확인
        2. approval_key가 없으면 새로 발급
        3. 웹소켓 연결 수립
        4. 실시간 데이터 수신 시작
        """
        try:
            # 1. 토큰 만료 확인
            if self._is_token_expired():
                self.logger.error(f"토큰이 만료되었습니다. (만료시간: {self.account_info.access_token_expired})")
                return
                
            # 2. approval_key 확인 및 발급
            if not self.account_info.approval_key:
                try:
                    self.account_info.approval_key = get_approval_key(
                        app_key=self.account_info.app_key,
                        app_secret=self.account_info.app_secret,
                        is_live=self.account_info.is_live
                    )
                    self.logger.info("✅ Approval key 발급 완료")
                except Exception as e:
                    self.logger.error(f"⚠ Approval key 발급 실패: {str(e)}", exc_info=True)
                    return
                
            # 3. 웹소켓 연결
            url = f"{self.websocket_url}"
            headers = {
                "Authorization": f"Bearer {self.account_info.kis_access_token}",
                "approval_key": self.account_info.approval_key
            }
            
            async with websockets.connect(url, extra_headers=headers) as websocket:
                self.websocket = websocket
                self.is_running = True
                self.logger.info(f"웹소켓 연결 성공 (계좌: {self.account_info.cano})")
                
                # 4. 실시간 데이터 수신
                while self.is_running:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if self.on_message:
                            self.on_message(data)
                            
                    except websockets.exceptions.ConnectionClosed:
                        self.logger.warning("웹소켓 연결이 종료되었습니다.")
                        break
                        
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON 디코딩 오류: {str(e)}")
                        continue
                        
                    except Exception as e:
                        self.logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"웹소켓 연결 중 오류 발생: {str(e)}", exc_info=True)
            raise
            
    async def disconnect(self) -> None:
        """웹소켓 연결 종료"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.logger.info("웹소켓 연결이 종료되었습니다.")

