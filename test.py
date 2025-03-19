import asyncio
import json
import websockets
import logging

# 한국투자증권(KIS) WebSocket URL
KIS_WEBSOCKET_URL = "wss://ops.koreainvestment.com:21000"
APPROVAL_KEY = "YOUR_ACCESS_TOKEN"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KISWebSocket")

async def subscribe_vi():
    """VI 발동 정보를 WebSocket으로 구독"""
    async with websockets.connect(KIS_WEBSOCKET_URL) as ws:
        subscribe_data = {
            "header": {
                "approval_key": APPROVAL_KEY,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0"  # VI 발동 TR ID
                }
            }
        }

        await ws.send(json.dumps(subscribe_data))
        logger.info("📡 VI 발동 구독 요청 완료")

        while True:
            message = await ws.recv()
            logger.info(f"📩 수신된 메시지: {message}")

            if message[0] in ['0', '1']:  # 실시간 데이터 구분
                recvstr = message.split('|')
                tr_id = recvstr[1]
                if tr_id == "H0STCNT0":
                    data = parse_vi_data(recvstr[3])
                    logger.info(f"⚡ VI 발동 감지: {data}")

def parse_vi_data(data: str) -> dict:
    """VI 발동 데이터 파싱"""
    fields = data.split('^')
    return {
        "stck_shrn_iscd": fields[0],  # 종목코드
        "vi_trgr_time": fields[1],    # VI 발동 시각
        "vi_trgr_prpr": fields[2],    # VI 발동 가격
        "vi_trgr_type": fields[3]     # VI 발동 유형 (1: 상한, 2: 하한)
    }

# 실행
asyncio.run(subscribe_vi())
