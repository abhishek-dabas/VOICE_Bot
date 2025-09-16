# file: core/vector_store.py

import chromadb
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader,
)
import os

# --- Configuration ---

# BAAI/bge-m3 is a powerful multilingual model that supports English and Hindi effectively.
# It's crucial for the bilingual requirement.
MODEL_NAME = "BAAI/bge-m3"

# It is a conditional assignment that determines which computing device to use for generating vector embeddings.
# The purpose of this is to optimize performance, by default it will be CPU but will check for GPU if available. 
# This pattern ensures that the code runs on any machine, regardless of whether it has a CUDA-enabled GPU.
# A developer or user can force the code to use the CPU (for example, to save GPU resources for other processes)
EMBEDDING_DEVICE = "cuda" if os.environ.get("CUDA_AVAILABLE") else "cpu" # use GPU if available. 
# The code evaluates whether the environment variable is present and has a "truthy" value(value means that the variable is defined, and its value is not empty or None).
# If the environment variable CUDA_AVAILABLE is present, the variable EMBEDDING_DEVICE is assigned the string value "cuda", indicating that a CUDA-compatible GPU should be used.

# Initialize ChromaDB client for persistence.
# In production, you would run ChromaDB as a separate server.
# For local demo, we use persistent storage on disk.
client = chromadb.PersistentClient(path="./chroma_db_store") 
# chromadb.PersistentClient(...): This command creates a ChromaDB client instance that is configured to be "persistent." This means that unlike an in-memory client, any data you store in the database will be saved to disk and will not be lost when the Python script or program ends.
# 1. Hosted/Managed ChromaDB
# How it works: You get an API key and a remote server address. The client connection code would look like this:
# import chromadb.utils.embedding_functions as embedding_functions
# client = chromadb.HttpClient(
#    host="your-chroma-host", 
#    port=443, 
#    ssl=True
#)
# Pros: Easy to set up, highly scalable, reliable, and requires minimal operational effort.
# Cons: You don't have full control over the infrastructure, and costs can increase with usage.
# 2. Self-Hosted ChromaDB Server (with Docker)
# Pros: Full control over your environment, more cost-effective for high usage, and can be integrated into existing infrastructure.
# Cons: Requires more operational knowledge and effort to manage, scale, and ensure high availability. 

# Initialize the embedding model once to reuse across the application.
embedding_function = HuggingFaceBgeEmbeddings(
    model_name = MODEL_NAME,
    model_kwargs = {"device": EMBEDDING_DEVICE}, # It is a dictionary that passes additional keyword arguments to the embedding model's initialization.
    encode_kwargs = {"normalize_embeddings": True}, # encode_kwargs is a dictionary that passes arguments to the encode method, which is called to generate the embeddings. 
    # "normalize_embeddings" - Recommended for BGE models. It ensures that the resulting embeddings have a unit norm (length of 1), which can improve performance in similarity searches and other tasks. 
    # Normalizing embeddings helps in maintaining consistency and can lead to better results when comparing vectors.
)

# -- Document Loading --

def get_document_loader(file_path: str):
    """Selects the appropriate document loader based on file extension."""
    _, extension = os.path.splitext(file_path) # This line uses os.path.splitext() from Python's built-in os module. This function splits a file path into two parts: the file's root (the part before the extension) and its extension.
    # For example, os.path.splitext("document.pdf") would return ('document', '.pdf').
    # The underscore (_) is a convention in Python for a variable that you don't intend to use. Here, we only need the extension part.
    extension = extension.lower()

    if extension == ".pdf":
        return PyPDFLoader(file_path)
    elif extension == ".docx":
        return Docx2txtLoader(file_path)
    elif extension == ".csv":
        return CSVLoader(file_path)
    elif extension == ".txt":
        return TextLoader(file_path)
    else:
        print(f"Warning: Unsupported file type '{extension}'. Skipping file.")
        return None
    
# -- Ingestion Logic --
# "File ingestion" is the process of collecting and importing data from various file formats into a system where it can be stored, processed, and analyzed.

def load_and_embed_documents(client_id: str, source_directory: str) -> bool:
    """Loads documents from a directory, processes them, and ingests them into
    a client-specific collection in ChromaDB.

    Args:
        client_id (str): The unique identifier for the client/tenant.
        source_directory (str): Path to the directory containing source documents.

    Returns:
        bool: True if ingestion was successful, False otherwise."""
    documents = []
    print(f"Starting ingestion for client '{client_id}' from '{source_directory}'...")

    # Iterate over files in the source directory
    for filename in os.listdir(source_directory): # os.listdir(source_directory) returns a list of strings, where each string is the name of a file or subdirectory located in the path specified by source_directory.
        file_path = os.path.join(source_directory, filename) # os.path.join(...) is used to create a full file path by combining the directory path (source_directory) with the filename (filename). 
        # This ensures that the correct path format is used for the operating system (/ on Unix-like systems, \ on Windows), making the code cross-platform compatible.
        loader = get_document_loader(file_path)
        if loader:
            try:
                documents.extend(loader.load())
                # loader.load(): This method call triggers the document loading process for a single file using the loader object. The load() method, provided by the LangChain document loader (like PyPDFLoader), reads the file's contents and returns a list of Document objects. 
                # Each Document object contains the text from the file and its associated metadata.
                # documents.extend(...): The extend() method is used to add the list of Document objects returned by loader.load() to the existing documents list. This way, all documents from all files in the directory are aggregated into a single list.
                # Example: If 2 files having these contents:
                # file1.txt: "Hello world.\n Page 2 content."
                # file2.txt: "This is a test."
                # After processing both files, documents would contain two Document objects:
                # [Document(page_content="Hello world.\n Page 2 content.", metadata={...}), Document(page_content="This is a test.", metadata={...})]
                # Each Document object includes the text content and metadata such as source file name, page number, etc.
                # If you had used documents.append(loader.load()), the result would be a nested list.
                print(f"Successfully loaded {filename}")
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    if not documents:
        print("No valid documents found for ingestion.")
        return False

    # Split documents into smaller chunks for better retrieval accuracy
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200) # chunk_size=1000: This sets the maximum target size for each chunk of text, measured in characters.
    # chunk_overlap=200: This sets the number of characters that will overlap between consecutive chunks. For example, the end of the first chunk will contain the first 200 characters of the second chunk. 
    # This overlap is vital for maintaining context when splitting documents, as it ensures that no important information is lost at the boundaries between chunks.
    splits = text_splitter.split_documents(documents) # It applies the splitting logic defined in the text_splitter instance to each document.
    # The output is a new list called splits, containing the smaller, processed Document chunks. The metadata from the original documents is preserved and copied to each of the new chunks.

    # Define collection name based on client ID for data isolation
    collection_name = f"client_{client_id}"

    # Create or update the vector store collection for this specific client
    # This automatically handles embedding generation and storage.
    try:
        Chroma.from_documents( # This is the core function call that performs the embedding and storage. It is a class method provided by the LangChain integration with ChromaDB.
            documents=splits,
            embedding=embedding_function,
            collection_name=collection_name, # If a collection with this name already exists, the documents will be added to it. If not, a new collection will be created.
            persist_directory="./chroma_db_store", # This ensures that the data persists across different runs of the program, so you don't have to re-ingest all the documents every time.
            client=client
        )
        print(f"Successfully ingested {len(splits)} chunks into collection '{collection_name}'.")
        return True
    except Exception as e:
        print(f"Error during vector store creation: {e}")
        return False

# -- Retrieval Logic --

def get_vector_retriever(client_id: str, k: int = 4): # k is the number of top-relevant documents chunks to retrieve for a given query.
    # It attempts to connect to a specific ChromaDB vector collection associated with that client_id
    """Initializes and returns a retriever for a specific client's collection.

    Args:
        client_id (str): The client identifier.
        k (int): Number of relevant documents to retrieve.

    Returns:
        Chroma.as_retriever or None: The configured retriever instance."""
    collection_name = f"client_{client_id}"
    try:
        vectorstore = Chroma( # This line initializes a Chroma object (a vector store instance) by reconnecting to the database on disk.
            persist_directory="./chroma_db_store", # Specifies the location of the persistent database files, the same one used during the ingestion phase.
            embedding_function=embedding_function, # This ensures that the vector store is aware of how the embeddings were generated, which is important for consistency in operations like similarity searches.
            collection_name=collection_name, # This specifies which client's collection to connect to. Each client has its own isolated collection based on their unique client_id.
            client=client # This passes the existing ChromaDB client instance to ensure that the connection settings (like the database path) are reused.
        )
        return vectorstore.as_retriever(search_kwargs={"k": k})
        # as_retriever(...): This method converts the Chroma vector store instance into a retriever object. A retriever is a specialized interface that allows for efficient querying of the vector store to find the most relevant documents based on a given input query.
        # search_kwargs={"k": k}: This argument specifies additional parameters for the retrieval process. Here, it sets the number of top relevant documents (k) to return for each query. This allows for flexibility in how many results you want to retrieve based on the application's needs.
    except Exception as e:
        # This can happen if the collection does not exist yet.
        print(f"Error initializing retriever for client '{collection_name}': {e}")
        return None