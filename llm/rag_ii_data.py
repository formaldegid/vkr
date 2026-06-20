from langchain_experimental.text_splitter import SemanticChunker
from langchain_ollama import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
import re

from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document
from qdrant_client import QdrantClient


embeddings = OllamaEmbeddings(model="embeddinggemma")

# Семантическое чанкование

# breakpoint_threshold_type может быть
# percentile, standard_deviation, interquartile

text_splitter = SemanticChunker(
    embeddings, 
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=90,
    #buffer_size=3
)


with open('RAG_data.txt','r') as t:
    texts = t.read()

texts = re.sub(r'\s+', ' ', texts)



# Чанки
docs = text_splitter.create_documents([texts])

min_length = 100
filtered_docs = [doc for doc in docs if len(doc.page_content) > min_length]

print(f"Создано чанков: {len(filtered_docs)}")
print(list(map(lambda x: len(x.page_content), filtered_docs)))

url = "http://localhost:6333"

collection_name = "docs1"

document_id = 'test1'

for doc in filtered_docs:
    doc.metadata["doc_id"] = document_id


vectorstore = QdrantVectorStore.from_documents(
    filtered_docs,
    embeddings,
    url=url,
    collection_name=collection_name,
    #force_recreate=True
)
print('done')

def delete_document_from_db(doc_id_to_delete):
    from qdrant_client import models
    vectorstore.client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.doc_id",
                    match=models.MatchValue(value=doc_id_to_delete),
                )
            ]
        ),
    )
    print(f"Документ {doc_id_to_delete} удален.")


#delete_document_from_db("test1")
