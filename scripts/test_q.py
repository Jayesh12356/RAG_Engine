import asyncio
import httpx

async def test_q():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/query", 
            json={"question": "What is a VPN?", "service_category": "GENERAL"}
        )
        data = resp.json()
        print("API Response:", data)

if __name__ == "__main__":
    asyncio.run(test_q())
