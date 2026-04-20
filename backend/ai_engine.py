import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.getenv("GROQ_API_KEY", "")
_client = Groq(api_key=_API_KEY) if _API_KEY else None

COMMAND_LIST = """
- open vscode
- open chrome
- open notepad
- open explorer
- open task manager
- open youtube
- play [query] on youtube
- youtube search [query]
- search [query]
- create folder named [name]
- create react app named [name]
- create python project named [name]
- start coding session
- take screenshot
- move cursor to center
- move cursor to top left
- move cursor to top right
- click
- right click
- double click
- scroll up
- scroll down
- press enter
- press escape
- press ctrl c
- press ctrl v
- press ctrl s
- press ctrl z
- press alt tab
- shutdown
- restart
- focus chrome
- focus edge
- focus vscode
- play 1
- play 2
- play 3
- play 4
- play 5
- first
- second
- third
"""

EXAMPLES = """
"open vs code" → "open vscode"
"launch vs code" → "open vscode"
"start coding" → "open vscode"
"launch editor" → "open vscode"
"play a song" → "play song on youtube"
"play music" → "play music on youtube"
"play something" → "play music on youtube"
"play sad songs" → "play sad songs on youtube"
"play [X]" → "play [X] on youtube"
"find lofi on youtube" → "youtube search lofi"
"search youtube for jazz" → "youtube search jazz"
"google python tutorial" → "search python tutorial"
"search for recipes" → "search recipes"
"browse google" → "open chrome"
"open browser" → "open chrome"
"open internet" → "open chrome"
"capture screen" → "take screenshot"
"grab screenshot" → "take screenshot"
"open files" → "open explorer"
"file manager" → "open explorer"
"create a folder called test" → "create folder named test"
"make a new folder named work" → "create folder named work"
"build react project" → "create react app named my-app"
"begin coding session" → "start coding session"
"start my work" → "start coding session"
"1" → "play 1"
"2" → "play 2"
"3" → "play 3"
"first one" → "first"
"second video" → "second"
"""


def interpret_command(user_input: str) -> str:
    if not _client:
        print("WARNING: GROQ_API_KEY not set")
        return user_input.lower().strip()

    try:
        prompt = f"""You are an AI OS automation assistant.
Convert user input into ONE exact command from the list below.

AVAILABLE COMMANDS:
{COMMAND_LIST}

CONVERSION EXAMPLES:
{EXAMPLES}

STRICT RULES:
1. Return ONLY the command on a single line
2. NO explanation, NO punctuation, NO quotes
3. NO "Command:" prefix
4. Match spacing exactly as shown
5. "open vscode" has NO space between vs and code
6. If input already matches a command return it unchanged
7. If nothing matches return the cleaned original input

User input: "{user_input}"

Command:"""

        response = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an OS automation assistant. Return ONLY the exact command, nothing else."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=50,
        )

        result = response.choices[0].message.content.strip()

        # Remove common AI prefixes
        for prefix in [
            "command:", "Command:", "COMMAND:",
            "output:", "Output:", "result:", "Result:",
            "answer:", "Answer:",
        ]:
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix):].strip()

        # Take only first line
        result = result.split('\n')[0].strip()

        # Remove surrounding quotes or backticks
        result = result.strip('"').strip("'").strip("`").strip()

        result = result.lower().strip()

        if not result:
            return user_input.lower().strip()

        print(f"AI: '{user_input}' → '{result}'")
        return result

    except Exception as e:
        print(f"AI Engine error: {e}")
        return user_input.lower().strip()


def get_ai_status() -> dict:
    if not _client:
        return {
            "status": "no_api_key",
            "message": "Set GROQ_API_KEY in .env file",
            "api_key_set": False
        }
    try:
        test_result = interpret_command("open chrome")
        return {
            "status": "working",
            "api_key_set": True,
            "test_input": "open chrome",
            "test_output": test_result,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "api_key_set": bool(_API_KEY)
        }