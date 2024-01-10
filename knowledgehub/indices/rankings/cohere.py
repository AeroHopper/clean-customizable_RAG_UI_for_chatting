from __future__ import annotations

import os

from kotaemon.base import Document

from .base import BaseReranking


class CohereReranking(BaseReranking):
    model_name: str = "rerank-multilingual-v2.0"
    cohere_api_key: str = os.environ.get("COHERE_API_KEY", "")
    top_k: int = 1

    def run(self, documents: list[Document], query: str) -> list[Document]:
        """Use Cohere Reranker model to re-order documents
        with their relevance score"""
        try:
            import cohere
        except ImportError:
            raise ImportError(
                "Please install Cohere " "`pip install cohere` to use Cohere Reranking"
            )

        cohere_client = cohere.Client(self.cohere_api_key)
        compressed_docs: list[Document] = []

        if not documents:  # to avoid empty api call
            return compressed_docs

        _docs = [d.content for d in documents]
        results = cohere_client.rerank(
            model=self.model_name, query=query, documents=_docs, top_n=self.top_k
        )
        for r in results:
            doc = documents[r.index]
            doc.metadata["relevance_score"] = r.relevance_score
            compressed_docs.append(doc)

        return compressed_docs
