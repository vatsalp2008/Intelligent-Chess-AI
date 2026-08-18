#!/usr/bin/env python3
"""
Minimal Ollama example: one prompt, then an interactive chat loop.

Used to check that Ollama is installed and a model is pulled before
pointing the chess bots at it.
"""

import sys

import ollama

MODEL = "llama3.2"


def main():
    try:
        response = ollama.generate(
            model=MODEL,
            prompt="Tell me a short story about a cat wandering in a dark forest.",
        )
    except Exception as exc:
        print(f"Could not reach Ollama: {exc}")
        print("Start it with 'ollama serve' and pull the model with "
              f"'ollama run {MODEL}'.")
        return 1

    print(response['response'])

    # Start a chat session and exchange messages
    print("\nChat below. Type 'quit' or press Ctrl-D to stop.\n")
    messages = []

    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_message.lower() in {"quit", "exit"}:
            break

        # Sending an empty turn just confuses the model
        if not user_message:
            continue

        messages.append({"role": "user", "content": user_message})

        try:
            chat_response = ollama.chat(model=MODEL, messages=messages)
        except Exception as exc:
            print(f"Chat failed: {exc}")
            break

        messages.append(chat_response['message'])
        print("Ollama:", chat_response['message']['content'])

    return 0


if __name__ == "__main__":
    sys.exit(main())
