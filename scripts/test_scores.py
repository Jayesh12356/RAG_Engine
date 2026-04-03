import asyncio
import httpx

QUESTIONS = [
    "What is a VPN?",
    "What are the key benefits of VPN?",
    "Compare LAN vs VPN?",
    "What is encryption in VPN?",
    "How does VPN work step-by-step?",
    "What is VPN tunneling?",
    "What are the types of VPN?",
    "Compare encapsulation vs encryption?",
    "Compare Transport Mode vs Tunnel Mode?",
    "Explain VPN protocols?",
    "Why use MFA in VPN?",
    "What are VPN limitations?",
    "Which VPN type would you use for a global company with multiple offices?",
    "Which protocol is best for high security and flexibility?",
    "When would PPTP still be used?",
    "How does VPN provide anonymity?",
    "Design a VPN solution for remote employees",
    "Which VPN is best for mobile users and why?",
    "Does VPN provide complete anonymity?",
    "Is encryption alone enough for a secure VPN?"
]

async def test_all():
    min_score = 1.0
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, q in enumerate(QUESTIONS, 1):
            resp = await client.post(
                "http://localhost:8000/query", 
                json={"question": q, "service_category": "GENERAL"}
            )
            data = resp.json()
            score = 0.0
            if data.get("sources"):
                score = data["sources"][0]["score"]
                if score < min_score:
                    min_score = score
            print(f"Q{i} Top Score: {score}")
        print(f"ABSOLUTE MINIMUM SCORE ACROSS 20 QUESTIONS: {min_score}")

if __name__ == "__main__":
    asyncio.run(test_all())
