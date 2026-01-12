import ollama

llm = "llama3.2"
response = ollama.generate(model=llm, prompt="Tell me a short story about a cat wandering in a dark forest.")
print(response['response'])

# Start a chat session and exchange messages
messages = []
while True:
    user_message = input("You: ")
    messages.append({"role": "user", "content": user_message})
    chat_response = ollama.chat(model=llm, messages=messages)
    messages.append(chat_response['message'])
    print("Ollama:", chat_response['message']['content'])