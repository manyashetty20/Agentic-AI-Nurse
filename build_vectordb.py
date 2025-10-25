import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
# --- THIS IS THE FIX ---
from langchain_community.document_loaders import DirectoryLoader # Use DirectoryLoader for text files
# --- END FIX ---

# Define paths
KB_PATH = "knowledge_base"
DB_PATH = "chroma_db"

def build_vector_database():
    """
    Builds a persistent vector database from documents
    in the knowledge_base folder.
    """
    print("Starting to build vector database...")
    
    # --- THIS IS THE FIX ---
    # Use DirectoryLoader to load all files in the directory
    # It automatically handles .txt files
    loader = DirectoryLoader(KB_PATH, glob="**/*.*", show_progress=True)
    documents = loader.load()
    # --- END FIX ---
    
    if not documents:
        print(f"CRITICAL ERROR: No documents found in the '{KB_PATH}' folder.")
        print("Please ensure your .txt files are inside that folder.")
        return

    print(f"Loaded {len(documents)} document(s).")

    # 2. Split the documents into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, # Smaller chunk size for better RAG on short files
        chunk_overlap=100
    )
    splits = text_splitter.split_documents(documents)
    print(f"Split documents into {len(splits)} chunks.")

    # 3. Initialize the embeddings model (runs locally)
    model_name = "all-MiniLM-L6-v2"
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={'device': 'cpu'} # Force CPU, or 'cuda' if you have a GPU
    )
    print(f"Loaded embeddings model: {model_name}")

    # 4. Create and persist the vector database
    print(f"Building vector database at: {DB_PATH}")
    vectordb = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    vectordb.persist()
    print(f"Successfully built and persisted vector database.")

if __name__ == "__main__":
    build_vector_database()