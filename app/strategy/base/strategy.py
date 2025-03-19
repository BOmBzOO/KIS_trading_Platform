"""기본 전략 클래스 정의"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Optional
from datetime import datetime

class BaseStrategy(ABC):
    """전략 기본 클래스"""
    
    def __init__(self, strategy_name: Optional[str] = None):
        self.strategy_name = strategy_name or self.__class__.__name__
        self.logger = logging.getLogger(f"Strategy.{self.strategy_name}")
        self.start_time = None
        self.is_running = False
    
    @abstractmethod
    async def process_data(self, data: Dict[str, Any]) -> None:
        """데이터 처리
        
        Args:
            data: 처리할 데이터 딕셔너리
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """전략 초기화
        전략 실행에 필요한 초기 설정을 수행합니다.
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """전략 정리
        전략 종료 시 필요한 정리 작업을 수행합니다.
        """
        pass
        
    async def start(self) -> None:
        """전략 시작"""
        if self.is_running:
            self.logger.warning("전략이 이미 실행 중입니다.")
            return
            
        try:
            await self.initialize()
            self.start_time = datetime.now()
            self.is_running = True
            self.logger.info(f"{self.strategy_name} 전략이 시작되었습니다.")
        except Exception as e:
            self.logger.error(f"전략 시작 중 오류 발생: {str(e)}")
            raise
            
    async def stop(self) -> None:
        """전략 종료"""
        if not self.is_running:
            return
            
        try:
            await self.cleanup()
            self.is_running = False
            duration = datetime.now() - self.start_time if self.start_time else None
            self.logger.info(f"{self.strategy_name} 전략이 종료되었습니다. 실행 시간: {duration}")
        except Exception as e:
            self.logger.error(f"전략 종료 중 오류 발생: {str(e)}")
            raise
            
    def get_strategy_info(self) -> Dict[str, Any]:
        """전략 정보 반환"""
        return {
            "name": self.strategy_name,
            "running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "running_time": str(datetime.now() - self.start_time) if self.start_time else None
        } 