import os
import subprocess
import time
import json
import threading
import webbrowser
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ─────────────────────────────────────────
# Groq SDK client
# ─────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

MAX_RETRIES = 3   # auto-retry attempts on AI / JSON errors

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _call_groq(prompt: str) -> str:
    """Call Groq and return the raw text response."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a JSON generator. "
                    "You ONLY output valid JSON. "
                    "Never use markdown. "
                    "Never add explanations outside the JSON."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=8000,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content.strip()


def _clean_json(raw: str) -> str:
    """Strip markdown fences and find outermost JSON object."""
    if raw.startswith("```json"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    elif raw.startswith("```"):
        raw = raw.replace("```", "").strip()
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{") : raw.rfind("}") + 1]
    return raw


def _normalize_file_content(content: str) -> str:
    """Convert escaped line breaks into real newlines so generated code preserves formatting."""
    if not isinstance(content, str):
        return content
    if "\n" not in content and "\\n" in content:
        content = content.replace("\\n", "\n")
    if "\\t" in content:
        content = content.replace("\\t", "\t")
    return content


def _is_react_project(description: str) -> bool:
    """Return True if the user wants a React / JSX app."""
    keywords = ["react", "jsx", "next.js", "nextjs", "vite react"]
    desc = description.lower()
    return any(k in desc for k in keywords)


def _run(cmd: str, cwd: str, capture: bool = False):
    """Run a shell command synchronously. Raises on non-zero exit."""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=capture,
        text=True
    )
    if result.returncode != 0:
        err = result.stderr.strip() if capture else ""
        raise RuntimeError(f"Command failed: {cmd}\n{err}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# REACT APP CREATOR  (fully automated — uses Vite scaffold)
# ─────────────────────────────────────────────────────────────────────────────

def _create_react_app(description: str, project_name: str = None):
    """
    Full end-to-end React app creation:
      1. Ask AI for ONLY the app-specific files (App.jsx, CSS, extra components)
      2. Scaffold a real project with  npx create-vite@latest <name> --template react
      3. Run  npm install
      4. Overwrite src/ with AI-generated code
      5. Open VS Code  +  start  npm run dev  in a new terminal window
    """

    # ── Step A: Ask AI for the React source files ─────────────────────────────
    react_prompt = f"""You are a React developer. Generate source files for a Vite React project.
Project idea: {description}

Return ONLY this JSON (no extra text):
{{
  "project_name": "my-app",
  "description": "short description",
  "files": {{
    "src/App.jsx": "FULL JSX CODE",
    "src/App.css": "FULL CSS CODE",
    "src/components/SomeComponent.jsx": "OPTIONAL EXTRA COMPONENT"
  }}
}}

Rules:
- project_name: lowercase-with-hyphens, no spaces
- files: ONLY src/ files — do NOT include package.json, vite.config.js, index.html, public/
- App.jsx must be a valid React functional component that renders everything
- App.css can be empty string "" if not needed
- Only add components/ files if the app genuinely needs them
- Write COMPLETE, WORKING code — no placeholders, no TODOs
- Use only built-in React and vanilla CSS — no extra npm packages unless listed below
- Allowed extra packages: react-router-dom, axios, react-icons
- If you use an extra package, add it to an optional key "extra_packages": ["package-name"]

CRITICAL: Response MUST start with {{ and end with }}. Nothing else."""

    last_error = None
    ai_output = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"🤖 Generating React source files... (attempt {attempt}/{MAX_RETRIES})")
            ai_output = _call_groq(react_prompt)
            ai_output = _clean_json(ai_output)
            data = json.loads(ai_output)

            if "files" not in data or not data["files"]:
                raise ValueError("AI returned no files.")

            # Resolve project name
            final_name = (
                project_name
                if project_name
                else data.get("project_name", "my-react-app")
            )
            final_name = final_name.replace(" ", "-").lower()

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            project_path = os.path.join(desktop, final_name)

            # ── Step B: Scaffold with Vite ────────────────────────────────
            print(f"⚛️  Scaffolding Vite React project '{final_name}'...")

            if os.path.exists(project_path):
                import shutil
                shutil.rmtree(project_path)   # remove old folder if re-creating

            _run(
                f'npx create-vite@latest "{final_name}" --template react',
                cwd=desktop,
                capture=True
            )
            print("   ✅ Vite scaffold done")

            # ── Step C: npm install ───────────────────────────────────────
            print("📦 Running npm install (this takes ~30 s)...")
            _run("npm install", cwd=project_path, capture=True)
            print("   ✅ npm install done")

            # Install any extra packages the AI requested
            extra_pkgs = data.get("extra_packages", [])
            if extra_pkgs:
                pkgs_str = " ".join(extra_pkgs)
                print(f"📦 Installing extra packages: {pkgs_str}...")
                _run(f"npm install {pkgs_str}", cwd=project_path, capture=True)
                print(f"   ✅ Extra packages installed")

            # ── Step D: Write AI source files into src/ ───────────────────
            print("✍️  Writing AI-generated source files...")
            created = []
            for rel_path, content in data["files"].items():
                if content is None:
                    continue

                content = _normalize_file_content(str(content))
                if not content.strip() and rel_path.endswith(".css"):
                    content = ""   # empty CSS is fine

                full_path = os.path.join(project_path, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                created.append(rel_path)
                print(f"   ✅ {rel_path}")

            # ── Step E: Open VS Code ──────────────────────────────────────
            time.sleep(0.5)
            subprocess.Popen(f'code "{project_path}"', shell=True)
            print("💻 Opened VS Code")

            # ── Step F: Start dev server in a new terminal window ─────────
            # Opens a new CMD window titled "React Dev Server" and runs npm run dev
            subprocess.Popen(
                f'start "React Dev Server - {final_name}" cmd /k "cd /d "{project_path}" && npm run dev"',
                shell=True
            )
            print("🚀 Dev server starting in new terminal window...")

            files_summary = ", ".join(created[:5])
            if len(created) > 5:
                files_summary += f" + {len(created) - 5} more"

            return (
                f"✅ React App Created: '{final_name}'\n"
                f"📝 AI Files: {files_summary}\n"
                f"💻 Opened in VS Code\n"
                f"🚀 Dev server running — open http://localhost:5173 in browser\n"
                f"📍 Location: Desktop/{final_name}"
            )

        except json.JSONDecodeError as e:
            last_error = f"JSON error: {e}"
            print(f"⚠️  Attempt {attempt} — bad JSON, retrying... ({last_error})")
            if attempt < MAX_RETRIES:
                time.sleep(1)

        except RuntimeError as e:
            last_error = str(e)
            print(f"⚠️  Attempt {attempt} — command failed, retrying...\n{last_error}")
            if attempt < MAX_RETRIES:
                time.sleep(2)

        except Exception as e:
            last_error = str(e)
            print(f"⚠️  Attempt {attempt} — unexpected error, retrying... ({last_error})")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    return (
        f"❌ React app creation failed after {MAX_RETRIES} attempts.\n"
        f"Last error: {last_error}\n"
        f"Try again or check your internet connection (npm install requires it)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC AI PROJECT CREATOR  (Python, HTML, Node, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def create_ai_project(project_description: str, project_name: str = None):
    """
    Creates a complete project using AI with auto-retry on errors.

    For React projects → delegates to _create_react_app() which uses Vite.
    For everything else → AI generates all files directly.

    Steps:
      1. Detect project type
      2. Generate project structure + code via Groq AI
      3. Create all files and folders on Desktop
      4. Open the project in VS Code
    """

    # Route React projects to the dedicated handler
    if _is_react_project(project_description):
        return _create_react_app(project_description, project_name)

    # ── Generic (non-React) project ───────────────────────────────────────────
    prompt = f"""You are a project generator. Create a JSON response for: {project_description}

Return ONLY this exact JSON structure (no extra text, no code blocks, no explanations):

{{
  "project_name": "snake_game",
  "project_type": "python",
  "description": "A simple terminal-based snake game",
  "structure": {{
    "main.py": "FULL_PYTHON_CODE_HERE",
    "README.md": "# Project Title\\n\\nInstructions here"
  }}
}}

Rules:
- project_name: lowercase_with_underscores for python, lowercase-with-hyphens for web
- project_type: python, html, nodejs
- structure: Each file path maps to COMPLETE working code — no placeholders
- For html: include index.html, style.css, script.js as separate files in one folder
- For html/css/js files: preserve real newline characters and proper indentation
- Do NOT emit all code in one line or combine files into one string
- For python: include main.py and README.md (add requirements.txt if needed)
- For nodejs: include index.js, package.json, README.md

CRITICAL: Your response must START with {{ and END with }}. Nothing else."""

    last_error = None
    ai_output = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"🤖 AI is analyzing your project idea... (attempt {attempt}/{MAX_RETRIES})")

            ai_output = _call_groq(prompt)
            print(f"📄 Received {len(ai_output)} characters from AI")

            ai_output = _clean_json(ai_output)
            project_data = json.loads(ai_output)

            if "structure" not in project_data or not project_data["structure"]:
                raise ValueError("AI didn't generate any files.")

            # Determine final project name
            final_name = (
                project_name
                if project_name
                else project_data.get("project_name", "my_project")
            )
            final_name = final_name.replace(" ", "_").lower()

            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            project_path = os.path.join(desktop, final_name)
            os.makedirs(project_path, exist_ok=True)
            print(f"📁 Created project folder: {final_name}")

            created_files = []
            for file_path, content in project_data["structure"].items():
                if content is None or not str(content).strip():
                    continue
                content = _normalize_file_content(str(content))
                full_path = os.path.join(project_path, file_path)
                parent = os.path.dirname(full_path)
                if parent and parent != project_path:
                    os.makedirs(parent, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                created_files.append(file_path)
                print(f"   ✅ {file_path}")

            if not created_files:
                raise ValueError("No files were written.")

            # For HTML projects: open the generated index.html automatically
            proj_type = project_data.get("project_type", "").lower()
            index_html_path = os.path.join(project_path, "index.html")
            if proj_type == "html" and os.path.exists(index_html_path):
                try:
                    webbrowser.open(f"file:///{index_html_path.replace(os.sep, '/')}")
                    print("🌐 Opened index.html in browser")
                except Exception as e:
                    print(f"⚠️ Could not open browser automatically: {e}")

            # For Node projects: run npm install automatically
            if proj_type == "nodejs" and os.path.exists(
                os.path.join(project_path, "package.json")
            ):
                print("📦 Running npm install for Node project...")
                try:
                    _run("npm install", cwd=project_path, capture=True)
                    print("   ✅ npm install done")
                except Exception as e:
                    print(f"   ⚠️  npm install warning: {e}")

                # Start the app automatically if package.json has a start script
                package_json_path = os.path.join(project_path, "package.json")
                try:
                    with open(package_json_path, "r", encoding="utf-8") as pj:
                        package_data = json.load(pj)
                    if package_data.get("scripts", {}).get("start"):
                        subprocess.Popen(
                            f'start "Node App - {final_name}" cmd /k "cd /d "{project_path}" && npm start"',
                            shell=True
                        )
                        print("🚀 Started Node app with npm start")
                except Exception as e:
                    print(f"   ⚠️ Could not auto-start Node app: {e}")

            # Open in VS Code
            time.sleep(0.5)
            subprocess.Popen(f'code "{project_path}"', shell=True)

            # Try to focus VS Code window
            time.sleep(1)
            try:
                import pygetwindow as gw
                wins = gw.getWindowsWithTitle("Visual Studio Code")
                if wins:
                    wins[0].activate()
            except Exception:
                pass

            files_summary = ", ".join(created_files[:5])
            if len(created_files) > 5:
                files_summary += f" + {len(created_files) - 5} more"

            return (
                f"✅ AI Project Created: '{final_name}'\n"
                f"📂 Type: {project_data.get('project_type', 'N/A')}\n"
                f"📝 Files: {files_summary}\n"
                f"💻 Opened in VS Code\n"
                f"📍 Location: Desktop/{final_name}"
            )

        except json.JSONDecodeError as e:
            last_error = f"JSON parsing error: {e}"
            print(f"⚠️  Attempt {attempt} failed (bad JSON) — retrying... ({last_error})")
            if attempt < MAX_RETRIES:
                time.sleep(1)

        except ValueError as e:
            last_error = str(e)
            print(f"⚠️  Attempt {attempt} failed (validation) — retrying... ({last_error})")
            if attempt < MAX_RETRIES:
                time.sleep(1)

        except Exception as e:
            last_error = str(e)
            print(f"⚠️  Attempt {attempt} failed (unexpected) — retrying... ({last_error})")
            if attempt < MAX_RETRIES:
                time.sleep(2)

    if ai_output:
        error_file = os.path.join(os.path.expanduser("~"), "Desktop", "ai_error_output.txt")
        try:
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(ai_output)
        except Exception:
            pass

    return (
        f"❌ Project creation failed after {MAX_RETRIES} attempts.\n"
        f"Last error: {last_error}\n"
        f"Raw AI output saved to: Desktop/ai_error_output.txt\n"
        f"Please try again or rephrase your command."
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND PARSER
# ─────────────────────────────────────────────────────────────────────────────

def parse_create_command(command: str):
    """
    Extracts project description and optional name from a natural-language command.

    Examples:
    - "build attendance tracker website using html css and javascript"
      → ("attendance tracker website using html css and javascript", None)
    - "build to do list project using html and css"
      → ("to do list project using html and css", None)
    - "create a snake game in python"
      → ("snake game in python", None)
    - "create project named todo-app for a task manager"
      → ("task manager", "todo-app")
    - "make me a calculator in react"
      → ("calculator in react", None)
    - "build a todo app in react"
      → ("todo app in react", None)
    """
    command = command.lower().strip()

    # Remove trigger words longest-first to avoid partial matches
    triggers = [
        "create ai project",
        "create project",
        "build me a",
        "build me",
        "make me a",
        "make me",
        "make a",
        "build a",
        "build",
        "create a",
        "create",
    ]
    for trigger in triggers:
        if command.startswith(trigger):
            command = command[len(trigger):].strip()
            break

    # Extract optional project name after "named" or "called"
    project_name = None
    description = command

    if "named" in command:
        parts = command.split("named", 1)
        description = parts[0].strip()
        if len(parts) > 1:
            name_part = parts[1].strip()
            if "for" in name_part:
                project_name = name_part.split("for")[0].strip()
                description = name_part.split("for")[1].strip() + " " + description
            else:
                project_name = name_part

    elif "called" in command:
        parts = command.split("called", 1)
        description = parts[0].strip()
        if len(parts) > 1:
            name_part = parts[1].strip()
            if "for" in name_part:
                project_name = name_part.split("for")[0].strip()
                description = name_part.split("for")[1].strip() + " " + description
            else:
                project_name = name_part

    if project_name:
        project_name = project_name.strip().replace(" ", "-")

    description = description.strip()
    if description.startswith("for "):
        description = description[4:].strip()

    return description, project_name