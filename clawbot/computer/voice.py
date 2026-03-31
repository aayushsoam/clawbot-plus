"""
🎙️ Voice Interface Module
Speech-to-Text (listening) and Text-to-Speech (speaking) for ClawBot.
"""
import os
import sys
import asyncio
import tempfile
from pathlib import Path
from rich.console import Console

console = Console()


# ════════════════════════════════════════════════════════
# 🎤 SPEECH-TO-TEXT (Listening)
# ════════════════════════════════════════════════════════

def listen(timeout: int = 10) -> str | None:
    """
    Record from microphone and transcribe to text.
    Uses SpeechRecognition with Google's free API.
    
    Returns:
        Transcribed text string, or None if failed.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        console.print("[red]❌ 'SpeechRecognition' install nahi hai. Run: pip install SpeechRecognition[/red]")
        return None
    
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 2.5  # Give the user time to think (2.5 seconds instead of 0.8)
    
    try:
        import concurrent.futures
        import subprocess
        import time
        import threading
        from rich.live import Live
        from rich.spinner import Spinner
        
        overlay_proc = None
        try:
            overlay_path = Path(__file__).parent / "overlay.py"
            flags = 0x08000000 if os.name == 'nt' else 0 # CREATE_NO_WINDOW
            # Pass our PID to the child so it knows when to die
            overlay_proc = subprocess.Popen([sys.executable, str(overlay_path), str(os.getpid())], creationflags=flags)
        except Exception as e:
            console.print(f"[dim]Warning: Floating UI could not be started: {e}[/dim]")

        audio = None
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            
            try:
                with console.status("[bold cyan]🎙️ Listening... (Bol rahe ho...)[/bold cyan]", spinner="bouncingBar"):
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=30)
            except KeyboardInterrupt:
                if overlay_proc:
                    try:
                        overlay_proc.terminate()
                    except Exception:
                        pass
                raise KeyboardInterrupt
                    
        if overlay_proc:
            try:
                overlay_proc.terminate()
            except Exception:
                pass
        
        with console.status("[dim]⏳ Transcribing...[/dim]", spinner="dots"):
            # Try Google first (free, no API key needed)
            try:
                text = recognizer.recognize_google(audio, language="hi-IN")
                console.print(f"[green]✅ Suna:[/green] {text}")
                return text
            except sr.UnknownValueError:
                # Try English if Hindi fails
                try:
                    text = recognizer.recognize_google(audio, language="en-US")
                    console.print(f"[green]✅ Heard:[/green] {text}")
                    return text
                except sr.UnknownValueError:
                    console.print("[yellow]⚠️ Samajh nahi aaya (Ya toh mic mute hai, ya Windows mein default mic galat set hai). Phir se koshish karein.[/yellow]")
                    return None
            except sr.RequestError as e:
                console.print(f"[red]❌ Google Speech API error: {e}[/red]")
                return None
            
    except sr.WaitTimeoutError:
        console.print("[yellow]⚠️ Koi awaaz nahi aayi. Timeout ho gaya.[/yellow]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Microphone error: {e}[/red]")
        console.print("[dim]Check karo ki microphone connected hai aur permission di hai.[/dim]")
        return None


# ════════════════════════════════════════════════════════
# 🔊 TEXT-TO-SPEECH (Speaking)
# ════════════════════════════════════════════════════════

async def speak_async(text: str, voice: str = "hi-IN-SwaraNeural"):
    """
    Convert text to speech using Microsoft Edge TTS (free, high quality).
    
    Popular voices:
        Hindi:   hi-IN-SwaraNeural (female), hi-IN-MadhurNeural (male)
        English: en-US-JennyNeural (female), en-US-GuyNeural (male)
        
    Args:
        text: Text to speak
        voice: Edge TTS voice name
    """
    try:
        import edge_tts
    except ImportError:
        console.print("[red]❌ 'edge-tts' install nahi hai. Run: pip install edge-tts[/red]")
        return
    
    if not text or not text.strip():
        return
    
    # Truncate very long text for speech
    speak_text = text[:1000] if len(text) > 1000 else text
    
    try:
        # Generate speech audio
        communicate = edge_tts.Communicate(speak_text, voice)
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        
        await communicate.save(tmp_path)
        
        # Play the audio
        _play_audio(tmp_path)
        
    except Exception as e:
        console.print(f"[red]❌ TTS error: {e}[/red]")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def speak(text: str, voice: str = "hi-IN-SwaraNeural"):
    """Synchronous wrapper for speak_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context, create a task
            asyncio.ensure_future(speak_async(text, voice))
        else:
            loop.run_until_complete(speak_async(text, voice))
    except RuntimeError:
        asyncio.run(speak_async(text, voice))


def _play_audio(file_path: str):
    """Play an audio file using available system tools."""
    import subprocess
    
    try:
        # Windows: use built-in media player
        if os.name == 'nt':
            # Use PowerShell to play audio (no external dependency needed)
            ps_cmd = (
                f"Add-Type -AssemblyName presentationCore; "
                f"$player = New-Object System.Windows.Media.MediaPlayer; "
                f"$player.Open('{file_path}'); "
                f"$player.Play(); "
                f"Start-Sleep -Seconds ([math]::Ceiling($player.NaturalDuration.TimeSpan.TotalSeconds + 1)); "
                f"$player.Close()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, timeout=60
            )
        else:
            # Linux/Mac: try mpv, ffplay, or aplay
            for player in ["mpv", "ffplay", "aplay"]:
                try:
                    subprocess.run([player, file_path], capture_output=True, timeout=60)
                    break
                except FileNotFoundError:
                    continue
    except Exception as e:
        console.print(f"[dim]Audio playback error: {e}[/dim]")


async def list_voices(language_filter: str = "hi") -> list[str]:
    """List available Edge TTS voices for a language."""
    try:
        import edge_tts
        voices = await edge_tts.list_voices()
        filtered = [v for v in voices if language_filter.lower() in v["Locale"].lower()]
        return [f"{v['ShortName']} ({v['Gender']})" for v in filtered]
    except ImportError:
        return ["edge-tts not installed"]
    except Exception as e:
        return [f"Error: {e}"]


# ════════════════════════════════════════════════════════
# 🔄 VOICE LOOP (for CLI integration)
# ════════════════════════════════════════════════════════

async def voice_mode_loop(llm):
    """
    Interactive voice loop: Listen → Process → Speak result.
    Runs until user says "band karo" / "stop" / "exit".
    """
    from .agent import run_computer_task
    
    console.print("\n[bold cyan]🎙️ Voice Mode Active[/bold cyan]")
    console.print("[dim]Bolo apna command... 'band karo' ya 'stop' bolne se exit hoga.[/dim]\n")
    
    stop_words = {"band karo", "stop", "exit", "quit", "ruk jao", "bas"}
    
    while True:
        text = listen(timeout=15)
        
        if text is None:
            continue
        
        # Check for stop commands
        if text.lower().strip() in stop_words:
            await speak_async("Theek hai boss, band kar raha hu.", "hi-IN-MadhurNeural")
            console.print("[yellow]🛑 Voice mode ended.[/yellow]")
            break
        
        # Process the command
        console.print(f"\n[bold]📝 Command:[/bold] {text}")
        
        try:
            # Immediate feedback so the user doesn't think it froze
            await speak_async("Abhi karta hu boss, thoda time dijiye.", "hi-IN-MadhurNeural")
            
            await run_computer_task(llm, text)
            # After task completion, speak a short confirmation
            await speak_async("Kaam ho gaya boss.", "hi-IN-MadhurNeural")
        except Exception as e:
            error_msg = f"Error aa gaya: {str(e)[:100]}"
            console.print(f"[red]❌ {error_msg}[/red]")
            await speak_async(error_msg, "hi-IN-MadhurNeural")

