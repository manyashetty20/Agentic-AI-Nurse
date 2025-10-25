# --- main.py ---

from fastapi import FastAPI
from pydantic import BaseModel
from agent_logic import agent_nurse_executor  # Import the agent
from langchain_core.messages import HumanMessage, AIMessage

# Initialize the FastAPI app
app = FastAPI()

# In-memory store for chat histories (for demo purposes)
# A real app would use MongoDB or another DB
chat_histories = {}

class ChatRequest(BaseModel):
    """Pydantic model for incoming chat requests"""
    user_id: str
    message: str

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint to handle patient interaction.
    """
    user_id = request.user_id
    user_message = request.message
    
    # Get or create the chat history for the user
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    
    chat_history = chat_histories[user_id]
    
    # Invoke the agent
    response = await agent_nurse_executor.ainvoke({
        "input": user_message,
        "chat_history": chat_history
    })
    
    ai_response = response.get("output", "I am sorry, I had an error.")
    
    # Update the chat history
    chat_history.append(HumanMessage(content=user_message))
    chat_history.append(AIMessage(content=ai_response))
    
    # Limit history size (e.g., last 10 messages)
    chat_histories[user_id] = chat_history[-10:]
    
    return {"response": ai_response}

@app.get("/")
def root():
    return {"status": "Agentic AI Nurse API is running"}

# To run this file:
# python -m uvicorn main:app --reload