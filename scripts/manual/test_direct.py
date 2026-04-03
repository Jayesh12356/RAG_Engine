import asyncio
from app.query.pipeline import QueryPipeline
from app.models.query import QueryRequest

async def run_pipeline():
    pipeline = QueryPipeline(demo_mode=False)

    questions = [
        "What is a VPN?",
        "Difference between LAN and VPN?",
        "How does a VPN work step-by-step?",
        "What are exceptions?",
        "Compare Transport Mode and Tunnel Mode"
    ]

    for q in questions:
        req = QueryRequest(question=q, service_category="VPN", top_k=5, rerank_top_n=3)
        print(f"\n\n====================\nQuestion: {q}\n")
        res = await pipeline.run(req)
        print(f"Confidence: {res.confidence}")
        print(f"Sources Output length: {len(res.sources)}")
        print(f"Answer:\n{res.answer}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
