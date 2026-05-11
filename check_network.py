import os
import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_connectivity():
    urls = [
        "https://api.telegram.org",
        "https://www.google.com",
        "https://generativelanguage.googleapis.com"
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls:
            try:
                logger.info(f"Testando conexão com {url}...")
                response = await client.get(url)
                logger.info(f"Sucesso! Status: {response.status_code}")
            except Exception as e:
                logger.error(f"Falha ao conectar com {url}: {e}")

if __name__ == "__main__":
    asyncio.run(check_connectivity())
