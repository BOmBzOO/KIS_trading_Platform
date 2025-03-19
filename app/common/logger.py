"""로깅 설정 모듈"""

import logging
import os
from datetime import datetime
from pathlib import Path
from app.common.constants import LogConfig, DateTimeConfig
import sys
from logging.handlers import RotatingFileHandler

class LoggerSetup:
    @classmethod
    def setup_logging(cls, log_level: int = logging.INFO) -> None:
        """로깅을 설정합니다.
        
        Args:
            log_level: 로깅 레벨 (기본값: logging.INFO)
        """
        # 로그 디렉토리 생성
        LogConfig.DIR.mkdir(exist_ok=True, parents=True)

        # 날짜별 로그 디렉토리 생성
        current_date = datetime.now().strftime(DateTimeConfig.DATE_FORMAT)
        date_log_dir = LogConfig.DIR / current_date
        date_log_dir.mkdir(exist_ok=True)

        # 로그 파일명 설정
        log_file = date_log_dir / LogConfig.FILENAME

        # 로깅 핸들러 설정
        handlers = [
            logging.StreamHandler(),  # 콘솔 출력
            logging.FileHandler(log_file, encoding='utf-8')  # 파일 출력
        ]

        # 로깅 설정 적용
        logging.basicConfig(
            level=log_level,
            format=LogConfig.FORMAT,
            handlers=handlers
        )

        # 외부 라이브러리 로깅 레벨 조정
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        
        # 로깅 시작 메시지
        logger = logging.getLogger(__name__)
        logger.info(f"로그 파일 경로: {log_file}")

    @classmethod
    def get_current_log_file(cls) -> Path:
        """현재 로그 파일의 경로를 반환합니다."""
        current_date = datetime.now().strftime(DateTimeConfig.DATE_FORMAT)
        return LogConfig.DIR / current_date / LogConfig.FILENAME

def setup_logger(
    log_level: str = "INFO",
    log_file: str = "vi_monitor.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """로거 설정
    
    Args:
        log_level (str): 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file (str): 로그 파일 경로
        max_bytes (int): 로그 파일 최대 크기 (바이트)
        backup_count (int): 보관할 로그 파일 수
    """
    # 로그 레벨 설정
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 로그 포맷 설정
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 추가
    try:
        # logs 디렉토리 생성
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 로그 파일 경로 설정
        log_file_path = log_dir / log_file
        
        # 파일 핸들러 설정
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
        
        logging.info(f"로그 파일이 생성되었습니다: {log_file_path}")
    except Exception as e:
        logging.error(f"로그 파일 생성 중 오류 발생: {str(e)}")
        logging.warning("파일 로깅이 비활성화되었습니다.") 