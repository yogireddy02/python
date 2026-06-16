import os, httpx, json, time

# We read the secret API key from an ENVIRONMENT VARIABLE instead of typing it in the notebook.
#   os.environ.get('OPENAI_API_KEY')  ->  looks up a variable named OPENAI_API_KEY that you set
#                                         in your terminal before starting Jupyter. Returns the
#                                         key string if it exists, or None if you never set it.
# Why not just paste the key here? Because anyone who sees your notebook would see your secret
# key and could run up charges on your account. Keeping it in the environment keeps it private.
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# This is the web address of OpenAI's chat endpoint - the 'door' we POST our question to.
OPENAI_URL = 'https://api.openai.com/v1/chat/completions'

# bool(...) turns the key into True (key exists) or False (key is None). We use this flag below
# so that every OpenAI cell can SKIP itself politely if you haven't set a key.
have_key = bool(OPENAI_API_KEY)
print('API key found - the OpenAI cells will run.' if have_key
      else 'No API key set - OpenAI cells will be skipped (everything else still works).')

if have_key:                              # only run if a key was found (see previous cell)
    response = httpx.post(                # POST because we are SENDING a question to the AI
        OPENAI_URL,                       # the chat endpoint address
        headers={                         # headers = extra labels attached to the request
            'Authorization': f'Bearer {OPENAI_API_KEY}'
            # ^ THE NEW IDEA: this header proves who you are. The format is the word 'Bearer',
            #   a space, then your key. 'Bearer' just means 'the holder of this key is allowed in'.
            #   Almost every paid API uses this exact header to check you're allowed.
        },
        json={                            # json= the body: the data we send, as a dict
            'model': 'gpt-4o-mini',       # which AI model to use (this one is small, fast, cheap)
            # Generate 3 different responses
            'n': 3,
            'messages': [                 # the conversation, as a list of messages
                # each message has a 'role' and the text 'content':
                {'role': 'system', 'content': 'You are a helpful ShopSmart assistant.'},  # sets behaviour
                {'role': 'user',   'content': 'Suggest a one-line slogan for a yoga mat.'}, # your question
            ],
        },
        timeout=30.0,    # wait up to 30 SECONDS - AI replies are slower than normal API calls,
                         # so we allow more time than the 10s we used for DummyJSON.
    )
    print('Status:', response.status_code)            # 200 = the AI answered successfully
    data = response.json()
    print(data) # turn the reply into a Python dict
    # The actual answer is buried inside the reply. We dig down to it:
    #   data['choices']         -> a list of possible answers (usually just one)
    #   [0]                     -> the first answer
    #   ['message']['content']  -> the actual text the AI wrote
    # reply = data['choices'][0]['message']['content']
    # print('AI reply:', reply)
    for message_id,ai_message in enumerate(data['choices']):
        print(f"AI reply:{message_id}:{ai_message['message']['content']}")

else:
    print('(skipped - no API key)')


if have_key:
    # Every reply includes a 'usage' section telling you how many TOKENS were used.
    # A token is roughly a piece of a word. You are billed per token, so this is your 'meter'.
    usage = data['usage']                                   # 'data' came from the previous cell
    print('Tokens you sent (prompt)    :', usage['prompt_tokens'])      # tokens in YOUR question
    print('Tokens the AI sent back     :', usage['completion_tokens'])  # tokens in the ANSWER
    print('Total tokens (what you pay) :', usage['total_tokens'])       # the two added together

    # Rough cost = (input tokens x input price) + (output tokens x output price).
    # These per-token prices are just examples - always check OpenAI's current pricing page.
    #   0.15/1_000_000  means '$0.15 per MILLION input tokens', written as price-per-single-token.
    in_rate  = 0.15 / 1_000_000     # dollars per input token  (illustrative)
    out_rate = 0.60 / 1_000_000     # dollars per output token (illustrative)
    cost = usage['prompt_tokens'] * in_rate + usage['completion_tokens'] * out_rate
    print(f'Rough cost of this one call : ${cost:.6f}')     # :.6f = show 6 decimal places
else:
    print('(skipped - no API key)')
