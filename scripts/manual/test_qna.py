import asyncio
import os
import httpx
from pydantic import BaseModel
from typing import List

# Ensure we're hitting the local dev server
API_URL = "http://localhost:8000/query"

# Define the sample questions to test
SAMPLE_QUESTIONS = [
    "What is a VPN?",
    "What are the key benefits of VPN?",
    "Difference between LAN and VPN?",
    "What is encryption in VPN?",
    "How does a VPN work step-by-step?",
    "What is VPN tunneling?",
    "What are types of VPN?",
    "What is encapsulation vs encryption?",
    "Compare Transport Mode and Tunnel Mode",
    "Explain VPN protocols with examples",
    "Why is MFA important in VPN?",
    "What are limitations of VPN?",
    "Which VPN type would you use for a global company with multiple offices?",
    "Which protocol is best for high security and flexibility?",
    "When would PPTP still be used?",
    "How does VPN provide anonymity?",
    "Design a VPN solution for remote employees",
    "Which VPN is best for mobile users and why?",
    "Does VPN make you completely anonymous?",
    "Is encryption alone enough for VPN security?"
]

async def test_questions():
    print("Starting tests against backend API...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, question in enumerate(SAMPLE_QUESTIONS, 1):
            print(f"\n--- Q{i}: {question} ---")
            try:
                response = await client.post(
                    API_URL,
                    json={"question": question, "service_category": "VPN"}
                )
                response.raise_for_status()
                data = response.json()
                print(f"Answer:\n{data.get('answer', 'NO ANSWER FIELDS FOUND')}")
                print(f"Confidence: {data.get('confidence')} ({data.get('confidence_label')})")
                print(f"Sources retrieved: {len(data.get('sources', []))}")
            except httpx.HTTPError as e:
                print(f"Error querying API: {e}")
            except Exception as e:
                print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_questions())
