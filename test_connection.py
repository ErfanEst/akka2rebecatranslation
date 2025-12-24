import os
import sys
from openai import OpenAI
from config.settings import settings

# Verify key loading
print(f"Loading key from settings...")
api_key = settings.OPENAI_API_KEY

if not api_key:
    print("❌ Error: OPENAI_API_KEY is missing in settings!")
    sys.exit(1)

print(f"✅ Key found: {api_key[:6]}...{api_key[-4:]}")

try:
    print("Connecting to OpenAI API...")
    client = OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model="gpt-4o",  # Use a standard model
        messages=[{"role": "user", "content": "Say 'Connection OK' if you hear me."}],
        max_tokens=10
    )
    
    print("\n✅ SUCCESS: API Connection Verified!")
    print(f"Response: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"\n❌ FAILURE: Connection Error")
    print(f"Error details: {str(e)}")
