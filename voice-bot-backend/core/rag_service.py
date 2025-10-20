# file: core/rag_service.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from core.vector_store import get_vector_retriever
from typing import Dict, Any

# Needed for Replacing the old process_query function
import os
import google.generativeai as genai
import asyncio

# New updates import
import traceback

SYSTEM_PROMPT_TEMPLATE = """
You are "Voice", a professional real estate assistant bot.
Your task is to answer user questions accurately based *only* on the provided context information.
If the context does not contain information to answer the question, state that you cannot find the specific details in your available documents. Do not make up information.
Greeting: Start the very first conversation with: 'Hello! My name is VOICE, how can I assist you today?'
Personalization: If a user shares their name ({user_name}), use it to address them in subsequent responses where appropriate (e.g., "Certainly, {user_name}, here is the information...").
Language: Respond entirely in {language_instruction}. Do not switch languages unless requested.
Context Information:
{context}
"""

def create_rag_chain(client_id: str):
    retriever = get_vector_retriever(client_id)
    if not retriever:
        raise ValueError(f"Could not initialize retriever for client {client_id}. Has data been ingested?")

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{question}"),
    ])

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    rag_chain = (
        {
            "context": retriever | format_docs,
            "question": lambda x: x["question"],
            "chat_history": lambda x: x["chat_history"],
            "language_instruction": lambda x: x["language_instruction"],
            "user_name": lambda x: x["user_name"],
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain

# Replace the old process_query function with this new one

# New update starts here
async def process_query(
    query: str,
    session_data: Dict[str, Any],
    client_id: str,
    rag_chain: Any
) -> str:
    print("--- CORRECT ASYNC DB CALL ---")
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        # 1. Get the retriever
        retriever = get_vector_retriever(client_id)
        if retriever is None:
            print(f"No retriever available for client {client_id}")
            return "I don't have any documents for this client. Please ingest documents first."

        # 2. Retrieve docs in thread
        print("--- Retrieving documents from ChromaDB... ---")
        docs = await asyncio.to_thread(retriever.get_relevant_documents, query)
        print(f"--- Retrieved {len(docs)} documents ---")
        if not docs:
            # Short-circuit and inform user (safer than calling LLM with empty context)
            return "I couldn't find relevant information in the uploaded documents."

        # Optional: print small snippet of first doc for debugging
        print("--- First doc snippet: ---")
        print(docs[0].page_content[:300])

        # 3. Build prompt + call Gemini
        context = "\n\n".join(doc.page_content for doc in docs)
        full_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        print("--- Calling Gemini AI... ---")
        response = await model.generate_content_async(full_prompt)

        # Depending on response object structure, ensure to access text safely
        text_out = getattr(response, "text", None) or response.get("candidates", [{}])[0].get("content", "")
        print("--- GEMINI CALL SUCCESSFUL ---")
        return text_out

    except Exception as e:
        print(f"--- AN ERROR OCCURRED: {e} ---")
        traceback.print_exc()
        return "Error: I encountered a problem while trying to generate a response."
    
# New update ends here