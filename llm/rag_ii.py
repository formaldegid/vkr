from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ollama
from langchain_qdrant import QdrantVectorStore
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient, models
import uvicorn
import traceback
from typing import List, Any
import os

app = FastAPI(title="AI RAG Server")

# Инициализация
try:
    embeddings = OllamaEmbeddings(model="embeddinggemma")
    url = "http://localhost:6333"
    collection_name = "docs1"
    client = QdrantClient(url=url)
    vectorstore = QdrantVectorStore(client=client, collection_name=collection_name, embedding=embeddings)
    
    count = vectorstore.client.count(collection_name=collection_name).count
    print(f"База успешно подключена. Записей: {count}")
except Exception as e:
    print(f"ОШИБКА ИНИЦИАЛИЗАЦИИ: {e}")

class AskRequest(BaseModel):
    prompt: str
    graph: List[Any] = []
    context_files: List[str] = []

@app.post('/ask')
async def ask_ai(request: AskRequest):
    print(f"Получен запрос: {request.prompt}") 
    try:
        # 1. Считывание перетащенных пользователем файлов
        direct_context = ""
        for f_id in request.context_files:
            file_path = f"../{f_id}.txt"
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        direct_context += f"[ВЫБРАННЫЙ ПОЛЬЗОВАТЕЛЕМ ФАЙЛ {f_id}]:\n{f.read()}\n\n"
                except Exception as e:
                    print(f"Ошибка чтения файла {f_id}: {e}")

        # 2. RAG-поиск без пользовательского контекста
        quest = request.prompt
        tips = vectorstore.similarity_search(
            query=quest,
            k=3,
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.doc_id",
                        match=models.MatchValue(value="test1"),
                    )
                ]
            )
        )
        
        context_fa = "\n\n".join([f"[Документ {i}]: {d.page_content}" for i, d in enumerate(tips[:3])])

        # 3. Полный контекст
        full_context = ""
        if direct_context:

            full_context += f"ОБЯЗАТЕЛЬНЫЙ КОНТЕКСТ (ИЗ ПРИЛОЖЕННЫХ ФАЙЛОВ):\n{direct_context}\n"
            
        full_context += f"ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ (ИЗ БАЗЫ ЗНАНИЙ):\n{context_fa}"

        print(full_context)
        
        # 4. Ollama
        response = ollama.chat(model='gemma3:4b', messages=[
            {'role': 'system', 'content': "Используй только предоставленные документы для ответа. Если в приложенных пользователем файлах есть ответ, отдавай предпочтение им."},
            {'role': 'user', 'content': f'Контекст:\n{full_context}\n\nВопрос:\n{request.prompt}'},
        ])

        return {'status': 'success', 'response': response['message']['content']}

    except Exception as e:
        print("--- ВНУТРЕННЯЯ ОШИБКА СЕРВЕРА ---")
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    print("Сервер запущен на http://127.0.0.1:8000")
    uvicorn.run(app, host='0.0.0.0', port=8000)
