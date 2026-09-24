import warnings
import uuid

from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")

checkpointer = InMemorySaver()
agent = create_agent(
    model = "google_genai:gemini-3.6-flash",
    tools = [],
    system_prompt = "You are an extremely helpful assistant.",
    checkpointer=checkpointer
)

def get_response(prompt: str, thread_id: str) -> dict:
    if not prompt.strip():
        return {"messages": []}
    

    config = {"configurable": {"thread_id": thread_id}}
    
    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]}, 
        config=config
    )
    return result

def main():
    session_thread_id = str(uuid.uuid4())
    print(f"--- Chat Session Started (Thread: {session_thread_id}) ---")

    while True:
        try:
            prompt = input("Input: ")
            if prompt.strip().lower() == "exit": 
                break
                
            response = get_response(prompt, thread_id=session_thread_id)

            if response["messages"]:
                print(f"Agent: {response['messages'][-1].content}")
                
        except EOFError:
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()