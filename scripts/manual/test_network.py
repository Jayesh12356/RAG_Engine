import asyncio
from app.query.pipeline import QueryPipeline
from app.models.query import QueryRequest

async def run_pipeline():
    pipeline = QueryPipeline(demo_mode=False)

    questions = [
        "What are some examples of domain names and their mapped IP addresses?"
    ]

    for q in questions:
        # Note: changing service_category to None or "d537f559-41d8-4bad-8cfd-9848d019f0dd NETWORK"
        req = QueryRequest(question=q, service_category=None, top_k=5, rerank_top_n=3)
        print(f"\n\n====================\nQuestion: {q}\n")
        res = await pipeline.run(req)
        print(f"Confidence: {res.confidence}")
        print(f"Sources Output length: {len(res.sources)}")
        for i, s in enumerate(res.sources):
            print(f"Source {i}: {s.pdf_name} - {s.text[:100]}")
        print(f"Answer:\n{res.answer}")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
