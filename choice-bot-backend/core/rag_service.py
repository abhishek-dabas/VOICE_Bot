# file: core/rag_service.py

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain.schema.output_parser import StrOutputParser
from core.vector_store import get_vector_retriever
from typing import Dict, Any

# --- System Prompt Template ---

# This prompt template guides the LLM to behave according to specific rules:
# 1. Use the provided context for answers.
# 2. Respond in the requested language (language_instruction).
# 3. Personalize the response if user_name is available.
# 4. Maintain a professional, helpful persona for "Choice Bot".

SYSTEM_PROMPT_TEMPLATE = """
You are "Choice", a professional real estate assistant bot.
Your task is to answer user questions accurately based *only* on the provided context information.
If the context does not contain information to answer the question, state that you cannot find the specific details in your available documents. Do not make up information.

Greeting: Start the very first conversation with: 'Hello! My name is CHOICE, how can I assist you today?'

Personalization: If a user shares their name ({user_name}), use it to address them in subsequent responses where appropriate (e.g., "Certainly, {user_name}, here is the information...").

Language: Respond entirely in {language_instruction}. Do not switch languages unless requested.

Context Information:
{context}
"""

# -- RAG Chain Construction --

def create_rag_chain(client_id: str):
    """Creates a Retrieval-Augmented Generation (RAG) chain using Google Generative AI for a specific client.

    Args:
        client_id (str): The client ID for the Google Generative AI service.

    Returns:
        A configured RAG chain ready for use.
    """
    retriever = get_vector_retriever(client_id)

    if not retriever:
        raise ValueError(f"Could not initialize retriever for client {client_id}. Has data been ingested?")
    
    # Initialize the Google Generative AI LLM
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3)
    # The temperature parameter controls the level of creativity and randomness in the language model's output. It influences the model's token selection.
    # A higher temperature (e.g., 0.8) makes the output more random and creative, while a lower temperature (e.g., 0.2) makes it more focused and deterministic.
    # In this case, a temperature of 0.3 is chosen to balance creativity and accuracy.
    # The change in temperature in an LLM does not directly increase or decrease the cost of the API calls.

    # Define the chat prompt structure, allowing for dynamic history and inputs
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_TEMPLATE), # The string "system" defines the role of this message, setting the context and instructions for how the AI should behave.
        MessagesPlaceholder(variable_name="chat_history"), # This inserts a placeholder for a list of past messages into the prompt.
        # When the prompt is executed, LangChain will dynamically insert the conversation history at this specific position, allowing the model to have memory of the past conversation turns.
        ("user", "{question}"), #The string "user" defines the role as coming from the user. "{question}" is a placeholder for the user's current query or question.
        # This allows the template to be reused with different user questions.   
    ])

    # RAG Chain Definition using LangChain Expression Language (LCEL)
    def format_docs(docs):
        """Converts retrieved documents into a single string context."""
        return "\n\n".join(doc.page_content for doc in docs) # This function takes a list of document objects (docs) and concatenates their page_content attributes into a single string, with two newline characters ("\n\n") separating each document's content.
        # "\n\n": This is the separator string. The Python join() method is called on this string, which means it is used as a separator between the contents of different documents.
        # In this case, two newline characters are used to clearly separate the content of different documents, improving readability for the LLM.
        # doc.page_content: For each doc object, it accesses its page_content attribute. In LangChain, a Document object has a page_content attribute that holds the text content from the source data.
        # The function returns a single string that combines the content of all documents, making it suitable for inclusion in the system prompt.

    rag_chain = (
        { # { ... } - This defines a RunnableParallel. This type of LangChain object takes a dictionary. It runs each dictionary value, which must be other runnables, in parallel.
            "context": retriever | format_docs, # The retriever is called with the input question to fetch relevant documents. The retrieved documents are then passed to the format_docs function to convert them into a single string context.
            "question": RunnablePassthrough(), # RunnablePassthrough(): This simply passes the user's question through unchanged. It keeps the original user question accessible later in the chain. 
            "chat_history": RunnablePassthrough(),
            "language_instruction": RunnablePassthrough(),
            "user_name": RunnablePassthrough(),
            # They pass the corresponding inputs (chat_history, language_instruction, and user_name) through the chain, making them available for later steps, such as populating the prompt template.
        }
        | RunnableLambda(lambda inputs: { # This lambda function takes the outputs from the previous step (the dictionary with context, question, chat_history, language_instruction, and user_name) and re-maps them to match the variable names expected in the prompt template.
            # Re-map inputs to match the prompt template variables exactly
            # This ensures that when the prompt is constructed, it has all the necessary information in the correct format.
            # |: The output of the previous block—a dictionary containing "context", "question", etc.—is piped to this component.
            # RunnableLambda(...): This wraps a standard Python function and converts it into a runnable component.
            # lambda inputs: { ... }: This is a short, anonymous function that takes a single argument, inputs.
            "context": inputs["context"], 
            "question": inputs["question"],
            "chat_history": inputs["chat_history"],
            "language_instruction": inputs["language_instruction"],
            "user_name": inputs["user_name"],
        })
        | prompt # The formatted inputs are then passed to the prompt template to generate the final prompt for the LLM.
        # prompt: This is a pre-defined PromptTemplate object. It takes the dictionary input and formats it into the final text that will be sent to the LLM.
        | llm # The generated prompt is sent to the Google Generative AI model to produce a response.
        # llm: This is a LangChain wrapper for a large language model (e.g., OpenAI's GPT or Google's Gemini). The LLM processes the prompt and generates a raw text response.
        | StrOutputParser() # Finally, the raw text output from the LLM is converted into a clean string format, removing any extra metadata or formatting from the model's raw response.
    )
    return rag_chain

# -- Session State and Query Processing --

def process_query(
        query: str, # query: str: The main input from the user (e.g., "What is a RAG system?").
        session_data: Dict[str, Any], # session_data: Dict[str, Any]: A dictionary containing current user's session-specific information such as chat history, user name, and language preference.
        client_id: str,
        rag_chain: Any # Type hint for the chain itself can be complex, use Any for simplicity. The LangChain Expression Language (LCEL) chain that performs the RAG logic.
) -> str:
    """
    Processes a user query using the RAG chain and session data.

    Args:
        query (str): The user's input question.
        session_data (Dict): Dictionary containing chat history, user name, and language.
        client_id (str): The client identifier.
        rag_chain (Runnable): The pre-built RAG chain instance.

    Returns:
        str: The generated response from the LLM.
    """
    language_map = {"en": "English", "hi": "Hindi"}
    language_instruction = language_map.get(session_data.get("language","en"), "English") # session_data.get("language", "en") safely retrieves the value for the "language" key. If the key doesn't exist, it defaults to "en".
    # The result is used to look up the full language name from the language_map dictionary. If that lookup fails (e.g., if a new, unmapped language code is added), it defaults to "English", providing a robust instruction for the LLM.

    # Prepare inputs for the RAG chain, including dynamic session values
    chain_input = {
        "question": query, # The user's current question. Sets the user's raw query.
        "chat_history": session_data.get("chat_history", []), # Default to empty list if no history
        "user_name": session_data.get("user_name", "user"), # Default value if name not captured
        "language_instruction": language_instruction,
    }

    # Execute the RAG chain to get the response
    response = rag_chain.invoke(chain_input) # The invoke method runs the entire RAG chain with the provided inputs, returning the final response from the LLM.
    return response
