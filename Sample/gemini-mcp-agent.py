import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv

load_dotenv()
# Get the Gemini API key from the environment variable
api_key = os.getenv("GEMINI_API_KEY")
# Get the BRAVE_API_KEY key from the environment variable
brave_api_key=os.getenv("BRAVE_API_KEY")
# Create Gemini instance LLM class
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro-exp-03-25",  # or "gemini-2.0-flash"
    temperature=0.7,
    max_retries=2,
    google_api_key=api_key,
)

async def main():
    async with MultiServerMCPClient(
        {
            "airbnb": {
                "command": "npx",
                "args": ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
                "transport": "stdio",
            },
            "brave_search": {
                "command": "npx",
                "args": ["-y", "@microagents/server-brave-search"],
                "transport": "stdio",
                "env": {
                    "BRAVE_API_KEY": brave_api_key
                }
            },
        }
    ) as client:
        # Create ReAct Agent with MCP servers
        graph = create_react_agent(model, client.get_tools())

        # Initialize conversation history using simple tuples
        inputs = {"messages": []}

        print("Agent is ready. Type 'exit' to quit.")
        while True:
            user_input = input("You: ")
            if user_input.lower() == "exit":
                print("Exiting chat.")
                break

            # Append user message to history
            inputs["messages"].append(("user", user_input))

            # call our graph with streaming to see the steps
            async for state in graph.astream(inputs, stream_mode="values"):
                last_message = state["messages"][-1]
                last_message.pretty_print()

            # update the inputs with the agent's response
            inputs["messages"] == state["messages"]


if __name__ == "__main__":
    asyncio.run(main())
