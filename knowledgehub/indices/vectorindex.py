from __future__ import annotations

import uuid
from typing import Optional, Sequence, cast

from kotaemon.base import BaseComponent, Document, RetrievedDocument
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.storages import BaseDocumentStore, BaseVectorStore

from .base import BaseIndexing, BaseRetrieval
from .rankings import BaseReranking

VECTOR_STORE_FNAME = "vectorstore"
DOC_STORE_FNAME = "docstore"


class VectorIndexing(BaseIndexing):
    """Ingest the document, run through the embedding, and store the embedding in a
    vector store.

    This pipeline supports the following set of inputs:
        - List of documents
        - List of texts
    """

    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings

    def to_retrieval_pipeline(self, *args, **kwargs):
        """Convert the indexing pipeline to a retrieval pipeline"""
        return VectorRetrieval(
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            embedding=self.embedding,
            **kwargs,
        )

    def to_qa_pipeline(self, *args, **kwargs):
        from .qa import CitationQAPipeline

        return TextVectorQA(
            retrieving_pipeline=self.to_retrieval_pipeline(**kwargs),
            qa_pipeline=CitationQAPipeline(**kwargs),
        )

    def run(self, text: str | list[str] | Document | list[Document]):
        input_: list[Document] = []
        if not isinstance(text, list):
            text = [text]

        for item in cast(list, text):
            if isinstance(item, str):
                input_.append(Document(text=item, id_=str(uuid.uuid4())))
            elif isinstance(item, Document):
                input_.append(item)
            else:
                raise ValueError(
                    f"Invalid input type {type(item)}, should be str or Document"
                )

        embeddings = self.embedding(input_)
        self.vector_store.add(
            embeddings=embeddings,
            ids=[t.id_ for t in input_],
        )
        if self.doc_store:
            self.doc_store.add(input_)


class VectorRetrieval(BaseRetrieval):
    """Retrieve list of documents from vector store"""

    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    top_k: int = 1

    def run(
        self, text: str | Document, top_k: Optional[int] = None, **kwargs
    ) -> list[RetrievedDocument]:
        """Retrieve a list of documents from vector store

        Args:
            text: the text to retrieve similar documents
            top_k: number of top similar documents to return

        Returns:
            list[RetrievedDocument]: list of retrieved documents
        """
        if top_k is None:
            top_k = self.top_k

        if self.doc_store is None:
            raise ValueError(
                "doc_store is not provided. Please provide a doc_store to "
                "retrieve the documents"
            )

        emb: list[float] = self.embedding(text)[0].embedding
        _, scores, ids = self.vector_store.query(embedding=emb, top_k=top_k)
        docs = self.doc_store.get(ids)
        result = [
            RetrievedDocument(**doc.to_dict(), score=score)
            for doc, score in zip(docs, scores)
        ]
        # use additional reranker to re-order the document list
        if self.rerankers:
            for reranker in self.rerankers:
                result = reranker(documents=result, query=text)

        return result


class TextVectorQA(BaseComponent):
    retrieving_pipeline: BaseRetrieval
    qa_pipeline: BaseComponent

    def run(self, question, **kwargs):
        retrieved_documents = self.retrieving_pipeline(question, **kwargs)
        return self.qa_pipeline(question, retrieved_documents, **kwargs)
