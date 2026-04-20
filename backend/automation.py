import subprocess
import os
import webbrowser
import urllib.request
import urllib.parse
import re
from ai_project_creator import create_ai_project, parse_create_command

# ─────────────────────────────────────────
# Store last search results so user can
# pick by number after seeing YouTube page
# ─────────────────────────────────────────
_last_search_results = []
_last_query = ""


def execute_command(command: str):
    global _last_search_results, _last_query
    command = command.lower().strip()

    # ─────────────────────────────────────────
    # 🖥️ APPS
    # ─────────────────────────────────────────

    if "open vscode" in command:
        subprocess.run("code", shell=True)
        return "VS Code opened ✅"

    elif "open chrome" in command:
        subprocess.run("start chrome", shell=True)
        return "Chrome opened ✅"

    elif "open notepad" in command:
        subprocess.run("notepad", shell=True)
        return "Notepad opened ✅"

    elif "open explorer" in command or "open files" in command:
        subprocess.run("explorer", shell=True)
        return "File Explorer opened ✅"

    elif "open task manager" in command:
        subprocess.run("taskmgr", shell=True)
        return "Task Manager opened ✅"

    # ─────────────────────────────────────────
    # 🎯 USER PICKS VIDEO BY NUMBER
    # This runs AFTER YouTube is already open
    # User sees results on screen then picks
    # ─────────────────────────────────────────
    # Supported:
    # "play 1" / "play 2" / "play 3"
    # "1" / "2" / "3"
    # "first" / "second" / "third"
    # "play first" / "play second"

    elif _last_search_results and (
        command.strip() in ["1", "2", "3", "4", "5"]
        or any(f"play {n}" in command for n in ["1","2","3","4","5"])
        or any(w in command for w in [
            "first", "second", "third", "fourth", "fifth"
        ])
    ):
        index = _get_video_index(command)

        if index is not None and index < len(_last_search_results):
            video = _last_search_results[index]
            video_url = (
                f"https://www.youtube.com/watch?v={video['id']}"
                f"&autoplay=1"
            )
            # Open video in new tab — replaces or opens beside search
            webbrowser.open(video_url)
            title = video["title"]
            # Clear results after playing
            _last_search_results = []
            return f"▶️ Playing video {index + 1}: '{title}'"

        else:
            total = len(_last_search_results)
            return (
                f"❌ Only {total} videos available. "
                f"Say 'play 1' to 'play {total}'"
            )

    # ─────────────────────────────────────────
    # ▶️ PLAY ON YOUTUBE
    # Fetches top result and opens the video directly (no search page)
    # ─────────────────────────────────────────
    # Supported commands:
    # "play kantara on youtube"
    # "play python tutorial on youtube"
    # "play on youtube: mr beast"
    # "youtube play lofi music"
    # "play ipl highlights on youtube"

    elif (
        ("play" in command and "youtube" in command)
        or "play on youtube" in command
        or "youtube play" in command
    ):
        query = ""

        if "play on youtube:" in command:
            query = command.split("play on youtube:")[-1].strip()

        elif "play on youtube" in command:
            query = command.split("play on youtube")[-1].strip()

        elif "youtube play" in command:
            query = command.split("youtube play")[-1].strip()

        elif "play" in command and "on youtube" in command:
            # "play kantara songs on youtube"
            after_play = command.split("play")[-1].strip()
            query = after_play.split("on youtube")[0].strip()

        elif "play" in command and "youtube" in command:
            # "play kantara youtube"
            after_play = command.split("play")[-1].strip()
            query = after_play.replace("youtube", "").strip()

        # Clean filler words
        filler = ["on", "the", "a", "an", "in", "at"]
        query = " ".join(
            [w for w in query.split() if w not in filler]
        ).strip()

        if query:
            _last_query = query

            # ── Fetch top results and open the #1 video directly ─────────
            results = _get_youtube_results(query, count=5)

            if results:
                _last_search_results = results
                # Open the top result directly with autoplay
                top = results[0]
                video_url = (
                    f"https://www.youtube.com/watch?v={top['id']}"
                    f"&autoplay=1"
                )
                webbrowser.open(video_url)
                return (
                    f"▶️ Playing: '{top['title']}'\n"
                    f"🔎 Query: '{query}'\n\n"
                    f"🎯 Want a different result? Say:\n"
                    f"'play 2' · 'play 3' · 'play 4' · 'play 5'"
                )
            else:
                # Fallback: open search page if video scraping failed
                search_url = (
                    f"https://www.youtube.com/results?search_query="
                    f"{query.replace(' ', '+')}"
                )
                webbrowser.open(search_url)
                return (
                    f"🔎 Couldn't auto-play — opened YouTube search for '{query}'"
                )
        else:
            webbrowser.open("https://www.youtube.com")
            return "YouTube opened ✅"

    # ─────────────────────────────────────────
    # 🎬 YOUTUBE SEARCH ONLY
    # ─────────────────────────────────────────
    # Supported:
    # "youtube search lofi"
    # "search on youtube python"
    # "search youtube for coding"
    # "find on youtube funny videos"
    # "open youtube"

    elif "youtube" in command:
        query = ""

        if "youtube search" in command:
            query = command.split("youtube search")[-1].strip()

        elif "search on youtube" in command:
            query = command.split("search on youtube")[-1].strip()

        elif "search youtube for" in command:
            query = command.split("search youtube for")[-1].strip()

        elif "find on youtube" in command:
            query = command.split("find on youtube")[-1].strip()

        else:
            after_youtube = command.split("youtube")[-1].strip()
            for word in ["search", "for", "find", "open", ":"]:
                after_youtube = after_youtube.replace(word, "").strip()
            query = after_youtube

        if query:
            url = (
                f"https://www.youtube.com/results?search_query="
                f"{query.replace(' ', '+')}"
            )
            webbrowser.open(url)
            return f"Searching YouTube for '{query}' 🎬"
        else:
            webbrowser.open("https://www.youtube.com")
            return "YouTube opened ✅"

    # ─────────────────────────────────────────
    # 🔍 GOOGLE SEARCH
    # ─────────────────────────────────────────

    elif "search" in command:
        query = command.replace("search", "").strip()
        if query:
            url = (
                f"https://www.google.com/search?q="
                f"{query.replace(' ', '+')}"
            )
            webbrowser.open(url)
            return f"Searching Google for '{query}' 🔍"
        else:
            webbrowser.open("https://www.google.com")
            return "Google opened ✅"

    # ─────────────────────────────────────────
    # 📁 FILE & PROJECT CREATION
    # ─────────────────────────────────────────

    elif "create folder" in command:
        if "named" in command:
            folder_name = command.split("named")[-1].strip()
        elif "called" in command:
            folder_name = command.split("called")[-1].strip()
        else:
            folder_name = "NewFolder"

        path = os.path.join(
            os.path.expanduser("~"), "Desktop", folder_name
        )
        os.makedirs(path, exist_ok=True)
        return f"Folder '{folder_name}' created on Desktop 📁"

    elif "create react app" in command:
        if "named" in command:
            app_name = (
                command.split("named")[-1].strip().replace(" ", "-")
            )
        elif "called" in command:
            app_name = (
                command.split("called")[-1].strip().replace(" ", "-")
            )
        else:
            app_name = "my-app"

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        subprocess.Popen(
            f"npx create-react-app {app_name}",
            shell=True,
            cwd=desktop
        )
        return f"Creating React app '{app_name}' on Desktop... ⚛️"

    elif "create python project" in command:
        if "named" in command:
            project_name = (
                command.split("named")[-1].strip().replace(" ", "_")
            )
        elif "called" in command:
            project_name = (
                command.split("called")[-1].strip().replace(" ", "_")
            )
        else:
            project_name = "my_python_project"

    # ─────────────────────────────────────────
    # 🤖 AI-POWERED PROJECT CREATION
    # ─────────────────────────────────────────
    # Supported commands:
    # "create ai project for a snake game in python"
    # "create project named todo-app for a task manager in react"
    # "build me a calculator app"
    # "make a weather dashboard in html css js"

    elif any(trigger in command for trigger in [
        "create ai project",
        "create project for",
        "create project",
        "create website",
        "build me",
        "make me a",
        "make me",
        "make a",
        "build a",
        "build",
        "create a",
        "create"
    ]):
        # ─────────────────────────────────────────
        # 🤖 AI-POWERED PROJECT CREATION
        # ─────────────────────────────────────────
        # Supported commands:
        # "create ai project for a snake game in python"
        # "create project named todo-app for a task manager in react"
        # "build me a calculator app"
        # "create project of portfolio website using react"
        # "create a todo list app in react"
        # "build attendance tracker website using html css and javascript"
        # "make a weather dashboard in html css js"
        
        # Extract description and optional name
        description, project_name = parse_create_command(command)
        
        if description:
            # Call AI to create the project
            result = create_ai_project(description, project_name)
            return result
        else:
            return (
                "❌ Please specify what project to create.\n"
                "Example: 'build attendance tracker website using html css'"
            )

    # ─────────────────────────────────────────
    # ⚡ WORKFLOW COMMANDS
    # ─────────────────────────────────────────

    elif "start coding session" in command:
        subprocess.run("code", shell=True)
        subprocess.run("start chrome", shell=True)
        folder_path = os.path.join(
            os.path.expanduser("~"), "Desktop", "TodayWork"
        )
        os.makedirs(folder_path, exist_ok=True)
        return (
            "Coding session started ⚡ "
            "VS Code + Chrome opened, TodayWork folder created"
        )

    # ─────────────────────────────────────────
    # 🎵 LOCAL MUSIC PLAYER / PLAYBACK
    # ─────────────────────────────────────────

    elif "play music" in command or "play song" in command or (
        "play" in command and any(word in command for word in [
            "track", "playlist", "audio", "song", "music"
        ])
    ):
        query = command.replace("play", "").strip()
        if query and not any(k in command for k in ["youtube", "on youtube"]):
            results = _get_youtube_results(query, count=5)
            if results:
                top = results[0]
                video_url = (
                    f"https://www.youtube.com/watch?v={top['id']}"
                    f"&autoplay=1"
                )
                webbrowser.open(video_url)
                return f"▶️ Playing: '{top['title']}' on YouTube"

        subprocess.run("start wmplayer", shell=True)
        return "Music player opened ✅"

    # ─────────────────────────────────────────
    # 💻 SYSTEM COMMANDS
    # ─────────────────────────────────────────

    elif "shutdown" in command:
        subprocess.run("shutdown /s /t 5", shell=True)
        return "PC will shutdown in 5 seconds ⚠️"

    elif "restart" in command:
        subprocess.run("shutdown /r /t 5", shell=True)
        return "PC will restart in 5 seconds ⚠️"

    # ─────────────────────────────────────────
    # ❌ NOT RECOGNIZED
    # ─────────────────────────────────────────

    else:
        return f"❌ Command not recognized: '{command}'"


# ─────────────────────────────────────────
# 🔧 HELPER — Fetch top YouTube results
# Returns list of {id, title}
# ─────────────────────────────────────────

def _get_youtube_results(query: str, count: int = 5):
    try:
        search_url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(query)
        )

        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        response = urllib.request.urlopen(req, timeout=5)
        html = response.read().decode("utf-8")

        # Extract video IDs
        video_ids = re.findall(
            r'"videoId":"([a-zA-Z0-9_-]{11})"', html
        )

        # Extract video titles
        video_titles = re.findall(
            r'"title":\{"runs":\[\{"text":"([^"]+)"', html
        )

        # Build results list — remove duplicates
        seen_ids = []
        results = []

        for vid in video_ids:
            if vid not in seen_ids:
                seen_ids.append(vid)
                idx = len(seen_ids) - 1
                title = (
                    video_titles[idx]
                    if idx < len(video_titles)
                    else f"Video {len(seen_ids)}"
                )
                results.append({"id": vid, "title": title})

            if len(results) >= count:
                break

        return results

    except Exception:
        return []


# ─────────────────────────────────────────
# 🔧 HELPER — Convert word/number to index
# "first" → 0, "play 2" → 1, "third" → 2
# ─────────────────────────────────────────

def _get_video_index(command: str):
    word_map = {
        "play 1": 0, "first":  0, "1": 0,
        "play 2": 1, "second": 1, "2": 1,
        "play 3": 2, "third":  2, "3": 2,
        "play 4": 3, "fourth": 3, "4": 3,
        "play 5": 4, "fifth":  4, "5": 4,
    }

    for key, index in word_map.items():
        if key in command:
            return index

    return None