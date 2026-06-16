import os
import httpx

# Read your OpenAI API key from an environment variable.
# This keeps the secret key out of your code.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# URL of the OpenAI Chat Completions endpoint.
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Check whether a key was found.
# bool(None) -> False
# bool("some text") -> True
have_key = bool(OPENAI_API_KEY)

# Let the user know whether API calls can be made.
print(
    "API key found - the OpenAI cells will run."
    if have_key
    else "No API key set - OpenAI cells will be skipped."
)

# List of user messages that will be sent one after another.
# Each response is added to the conversation history so the AI
# remembers previous messages.
user_message_list = [
    "Suggest a one-line slogan for a yoga mat.",
    "Can you make it more energetic?"
]


def play_messages(user_message_list):
    """
    Sends a sequence of messages to the OpenAI API while
    maintaining conversation history.

    Parameters:
        user_message_list (list): List of user prompts.

    Returns:
        conv_history (list): Full conversation history.
    """

    # If there is no API key, stop immediately.
    if not have_key:
        print("No API key available.")
        return

    # Stores the entire conversation.
    # Example:
    # [
    #   {"role": "user", "content": "..."},
    #   {"role": "assistant", "content": "..."}
    # ]
    conv_history = []

    # System messages tell the model how to behave.
    # They are sent with every API request.
    system_message = [
        {
            "role": "system",
            "content": "You are a helpful ShopSmart assistant."
        }
    ]
    conv_history = conv_history + system_message

    # Loop through every user message.
    for user_message in user_message_list:

        # Display the current user message.
        print(f"\nUser: {user_message}")

        # Add the user message to conversation history.
        conv_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            # Send a POST request to OpenAI.
            response = httpx.post(

                # API endpoint
                OPENAI_URL,

                # Authentication header.
                # The word "Bearer" is the standard format used by APIs.
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                },

                # JSON body sent to the API.
                json={

                    # Model to use.
                    "model": "gpt-4o-mini",

                    # Combine system message and conversation history.
                    # This allows the model to remember previous turns.
                    "messages":  conv_history
                },

                # Maximum time to wait before giving up.
                timeout=30.0
            )

            # Raise an exception if the server returned
            # an error such as 401, 404, or 500.
            response.raise_for_status()

            # Convert the JSON response into a Python dictionary.
            data = response.json()

            # Extract the assistant's reply.
            # Response structure:
            # {
            #   "choices": [
            #       {
            #           "message": {
            #               "role": "assistant",
            #               "content": "..."
            #           }
            #       }
            #   ]
            # }
            reply = data["choices"][0]["message"]["content"]

            # Print the AI response.
            print(f"Assistant: {reply}")

            # Store the assistant response so future API calls
            # include it as context.
            conv_history.append({
                "role": "assistant",
                "content": reply
            })

        except Exception as e:
            # If something goes wrong, print the error
            # and stop the conversation loop.
            print("Error:", e)
            break

    # Return the entire conversation history.
    return conv_history


# Run the conversation.
history = play_messages(user_message_list)

# Print the complete conversation history.
print("\nFinal conversation history:")

for msg in history:
    print(f"{msg['role']}: {msg['content']}")