import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

print("Connecting to Claude...")

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": """You are an FPL expert assistant. 
            
            A player profile:
            - Name: Mohamed Salah
            - Price: £13.0m
            - Total points: 180
            - Form: 8.2
            - Next fixture: vs Manchester United (home)
            - Fixture difficulty: 2/5 (easy)
            
            Should I captain him this gameweek? Give me exactly 3 sentences — confident, direct, no fluff."""
        }
    ]
)

print("✅ Claude API working!")
print()
print(message.content[0].text)