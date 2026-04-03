import asyncio
import json
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
    async with httpx.AsyncClient(timeout=120.0) as client:
        results = []
        for i, q in enumerate(QUESTIONS, 1):
            print(f"\\n--- Q{i}: {q} ---")
            resp = await client.post(
                "http://localhost:8000/query", 
                json={"question": q, "service_category": "GENERAL"}
            )
            data = resp.json()
            answer = data.get("answer", "")
            conf = data.get("confidence_label", "")
            score = data.get("confidence", 0)
            print(f"Confidence: {conf} ({score})")
            print(f"Answer: {answer}\\n")
            results.append((q, conf, answer))
            
        # Summary
        refusals = [r for r in results if r[1] == "refused"]
        print(f"\\nTotal Questions: {len(results)}")
        print(f"Refusals: {len(refusals)}")
        for r in refusals:
            print(f"FAILED (Refused): {r[0]}")

if __name__ == "__main__":
    asyncio.run(test_all())
