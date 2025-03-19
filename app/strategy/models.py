"""전략 관련 모델 정의"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class VIData:
    """VI 발동 데이터"""
    symbol: str                # 종목 코드
    symbol_name: str          # 종목명
    vi_trgr_time: str        # VI 발동 시각
    vi_trgr_price: float     # VI 발동 가격
    vi_trgr_type: str        # VI 발동 유형
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VIData':
        """딕셔너리에서 VI 데이터 생성"""
        body = data.get("body", {})
        output = body.get("output", {})
        
        return cls(
            symbol=output.get("symbol", ""),
            symbol_name=output.get("symbol_name", ""),
            vi_trgr_time=output.get("vi_trgr_time", ""),
            vi_trgr_price=float(output.get("vi_trgr_price", 0)),
            vi_trgr_type=output.get("vi_trgr_type", "")
        )
        
    def __str__(self) -> str:
        return (
            f"VI 발동 - 종목: {self.symbol_name}({self.symbol}), "
            f"시각: {self.vi_trgr_time}, "
            f"가격: {self.vi_trgr_price}, "
            f"유형: {self.vi_trgr_type}"
        ) 