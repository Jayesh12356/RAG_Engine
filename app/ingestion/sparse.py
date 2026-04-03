from rank_bm25 import BM25Okapi

class BM25SparseEncoder:
    def __init__(self):
        self.bm25 = None
    
    def fit(self, corpus: list[str]) -> None:
        tokenized_corpus = [doc.lower().split() for doc in corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
    def encode(self, text: str) -> dict[int, float]:
        if not self.bm25:
            return {}
        
        tokens = text.lower().split()
        sparse_vec = {}
        
        for token in set(tokens):
            if token in self.bm25.idf:
                idf = self.bm25.idf[token]
                tf = tokens.count(token)
                
                doc_len = len(tokens)
                avgdl = self.bm25.avgdl
                
                # BM25 term frequency weight for this document
                num = tf * (self.bm25.k1 + 1)
                den = tf + self.bm25.k1 * (1 - self.bm25.b + self.bm25.b * doc_len / avgdl)
                score = idf * (num / den)
                
                if score > 0:
                    token_id = hash(token) % 30000
                    sparse_vec[token_id] = float(score)
        
        return sparse_vec
        
    def encode_batch(self, texts: list[str]) -> list[dict[int, float]]:
        return [self.encode(t) for t in texts]
