"""인증 서비스"""

import os
import aiohttp
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta
from .models import AccountInfo
from app.common.constants import APIConfig, EnvKeys
from app.common.utils import save_account_info_to_env
from dotenv import load_dotenv

class AuthService:
    """인증 서비스
    
    외부 서버와의 인증 및 계좌 정보 조회를 담당하는 서비스입니다.
    HTTP 세션 관리와 인증 토큰 관리를 수행합니다.
    """
    
    def __init__(self, base_url: str = APIConfig.EXTERNAL_BASE_URL):
        """
        Args:
            base_url: API 기본 URL (기본값: APIConfig.EXTERNAL_BASE_URL)
        """
        load_dotenv()
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self.account_info: Optional[AccountInfo] = None
        self.logger = logging.getLogger("AuthService")
        
        # 환경 변수에서 필수 정보 로드
        self.username = os.getenv(EnvKeys.EXTERNAL_USERNAME)
        self.password = os.getenv(EnvKeys.EXTERNAL_PASSWORD)
        self.cano = os.getenv(EnvKeys.CANO)
        
        if not all([self.username, self.password, self.cano]):
            missing = []
            if not self.username: missing.append(EnvKeys.EXTERNAL_USERNAME)
            if not self.password: missing.append(EnvKeys.EXTERNAL_PASSWORD)
            if not self.cano: missing.append(EnvKeys.CANO)
            self.logger.error(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing)}")
            raise ValueError(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing)}")
        
    async def initialize(self) -> None:
        """서비스 초기화
        
        HTTP 세션을 초기화합니다.
        """
        if not self._session:
            self._session = aiohttp.ClientSession()  # trust_env 제거
            self.logger.info("HTTP 세션이 초기화되었습니다.")
            
    async def close(self) -> None:
        """서비스 종료
        
        HTTP 세션을 종료하고 리소스를 정리합니다.
        """
        if self._session:
            await self._session.close()
            self._session = None
            self.logger.info("HTTP 세션이 종료되었습니다.")
            
    def _get_kst_now(self) -> datetime:
        """현재 한국 시간을 반환합니다."""
        return datetime.now(tz=timezone(timedelta(hours=9)))
            
    def _parse_expired_time(self, expired_str: str) -> datetime:
        """만료 시간 문자열을 datetime 객체로 변환
        
        Args:
            expired_str: ISO 형식의 만료 시간 문자열 (예: "2024-03-19T15:30:00+09:00")
            
        Returns:
            datetime: 한국 시간 기준의 만료 시간
        """
        try:
            # KST 시간대 설정
            kst = timezone(timedelta(hours=9))
            
            # +09:00이 있는 경우 제거
            if "+09:00" in expired_str:
                expired_str = expired_str.replace("+09:00", "")
                
            # datetime으로 파싱하고 KST 시간대 설정
            dt = datetime.fromisoformat(expired_str)
            dt = dt.replace(tzinfo=kst)
            
            return dt
            
        except Exception as e:
            self.logger.error(f"만료 시간 파싱 중 오류 발생: {str(e)}")
            raise ValueError(f"잘못된 만료 시간 형식: {expired_str}")
            
    def _load_saved_account_info(self) -> Optional[AccountInfo]:
        """저장된 계좌 정보 로드
        
        .env 파일에서 저장된 계좌 정보를 로드합니다.
        토큰이 만료되지 않은 경우에만 계좌 정보를 반환합니다.
        
        Returns:
            Optional[AccountInfo]: 계좌 정보 (토큰이 만료된 경우 None)
        """
        try:
            # 필수 환경 변수 확인
            required_keys = [
                "KIS_ACCESS_TOKEN",
                "ACCESS_TOKEN_EXPIRED",
                "HTS_ID",
                "APP_KEY",
                "APP_SECRET",
                "CANO"
            ]
            
            # 환경 변수가 모두 있는지 확인
            if not all(os.getenv(key) for key in required_keys):
                self.logger.info("저장된 계좌 정보가 없습니다.")
                return None
            
            # 토큰 만료 시간 확인
            expired_str = os.getenv("ACCESS_TOKEN_EXPIRED")
            if not expired_str:
                return None
                
            # 만료 시간 파싱 및 확인
            expired_time = self._parse_expired_time(expired_str)
            now = self._get_kst_now()
            
            if now >= expired_time:
                self.logger.warning(f"저장된 토큰이 만료되었습니다. (만료시간: {expired_time.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                return None
                
            # AccountInfo 객체 생성
            account_info = AccountInfo(
                kis_access_token=os.getenv("KIS_ACCESS_TOKEN"),
                access_token_expired=expired_time,
                hts_id=os.getenv("HTS_ID"),
                app_key=os.getenv("APP_KEY"),
                app_secret=os.getenv("APP_SECRET"),
                cano=os.getenv("CANO"),
                approval_key=os.getenv("APPROVAL_KEY"),
                is_live=os.getenv("IS_LIVE", "true").lower() == "true",
                acnt_prdt_cd=os.getenv("ACNT_PRDT_CD", "01"),
                acnt_type=os.getenv("ACNT_TYPE", "live"),
                acnt_name=os.getenv("ACNT_NAME", ""),
                owner_name=os.getenv("OWNER_NAME", ""),
                owner_id=os.getenv("OWNER_ID", ""),
                id=os.getenv("ID", "")
            )
            
            self.logger.info(f"저장된 계좌 정보를 로드했습니다. (계좌: {account_info.cano})")
            self.logger.info(f"토큰 만료 시간: {expired_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return account_info
            
        except Exception as e:
            self.logger.error(f"저장된 계좌 정보 로드 중 오류 발생: {str(e)}")
            return None
            
    async def authenticate(self) -> AccountInfo:
        """인증 수행 및 계좌 정보 조회
        
        1. 저장된 계좌 정보가 있고 토큰이 유효한 경우 해당 정보를 사용
        2. 그렇지 않은 경우 외부 서버에 로그인하여 새로운 계좌 정보 조회
        """
        try:
            # 1. 저장된 계좌 정보 확인
            saved_account = self._load_saved_account_info()
            if saved_account:
                self.account_info = saved_account
                self.logger.info("저장된 계좌 정보를 사용합니다.")
                return saved_account
                
            # 2. 새로운 인증 수행
            self.logger.info("새로운 인증을 시도합니다...")
            token = await self._login(self.username, self.password)
            
            # 3. 계좌 정보 조회
            self.logger.info("계좌 정보 조회 중...")
            self.account_info = await self._get_account_info(token)
            
            # 4. 계좌 정보 저장
            save_account_info_to_env(
                kis_access_token=self.account_info.kis_access_token,
                access_token_expired=self.account_info.access_token_expired,
                approval_key=self.account_info.approval_key,
                hts_id=self.account_info.hts_id,
                app_key=self.account_info.app_key,
                app_secret=self.account_info.app_secret,
                cano=self.account_info.cano,
                is_live=self.account_info.is_live,
                acnt_prdt_cd=self.account_info.acnt_prdt_cd,
                acnt_type=self.account_info.acnt_type,
                acnt_name=self.account_info.acnt_name,
                owner_name=self.account_info.owner_name,
                owner_id=self.account_info.owner_id,
                id=self.account_info.id
            )
            self.logger.info(f"새로운 계좌 정보가 저장되었습니다. (계좌: {self.account_info.cano})")
            
            return self.account_info
            
        except Exception as e:
            self.logger.error(f"인증 중 오류 발생: {str(e)}")
            raise
            
    async def _login(self, username: str, password: str) -> str:
        """외부 서버 로그인
        
        Args:
            username: 사용자 아이디
            password: 비밀번호
            
        Returns:
            str: 액세스 토큰
        """
        if not self._session:
            await self.initialize()
            
        url = f"{self.base_url}/api/v1/login/access-token"
        self.logger.debug(f"로그인 요청: {url}")
        
        try:
            # OAuth2 password grant 형식으로 변경
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": "",
                "client_id": "",
                "client_secret": ""
            }
            
            async with self._session.post(url, data=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"로그인 실패: {error_text}")
                    raise Exception(f"로그인 실패: {error_text}")
                    
                data = await response.json()
                self.logger.info("로그인 성공")
                return data["access_token"]
                
        except Exception as e:
            self.logger.error(f"로그인 요청 중 오류 발생: {str(e)}")
            raise
            
    async def _get_account_info(self, access_token: str) -> AccountInfo:
        """계좌 정보 조회
        
        Args:
            access_token: 액세스 토큰
            
        Returns:
            AccountInfo: 계좌 정보
        """
        if not self._session:
            await self.initialize()
            
        url = f"{self.base_url}/api/v1/accounts"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            async with self._session.get(url, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"계좌 정보 조회 실패: {error_text}")
                    raise Exception(f"계좌 정보 조회 실패: {error_text}")
                    
                data = await response.json()
                self.logger.debug(f"계좌 정보 응답: {data}")
                
                # data 배열에서 현재 계좌번호와 일치하는 계좌 정보 찾기
                account_list = data.get("data", [])
                account_data = None
                for account in account_list:
                    if account.get("cano") == self.cano:
                        account_data = account
                        break
                        
                if not account_data:
                    raise Exception(f"계좌번호 {self.cano}에 해당하는 계좌 정보를 찾을 수 없습니다.")
                    
                # AccountInfo 객체 생성
                account_info = AccountInfo(
                    kis_access_token=account_data.get("kis_access_token"),
                    access_token_expired=account_data.get("access_token_expired"),
                    hts_id=account_data.get("hts_id"),
                    app_key=account_data.get("app_key"),
                    app_secret=account_data.get("app_secret"),
                    cano=account_data.get("cano"),
                    approval_key=account_data.get("approval_key"),
                    is_live=account_data.get("acnt_type") == "live",
                    acnt_prdt_cd=account_data.get("acnt_prdt_cd", "01"),
                    acnt_type=account_data.get("acnt_type", "live"),
                    acnt_name=account_data.get("acnt_name", ""),
                    owner_name=account_data.get("owner_name", ""),
                    owner_id=account_data.get("owner_id", ""),
                    id=account_data.get("id", ""),
                    discord_webhook_url=account_data.get("discord_webhook_url", ""),
                    is_active=account_data.get("is_active", True)
                )
                
                self.logger.info(f"계좌 정보 조회 성공 (계좌: {account_info.cano})")
                return account_info
                
        except Exception as e:
            self.logger.error(f"계좌 정보 조회 중 오류 발생: {str(e)}")
            raise 