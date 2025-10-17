"""
Minimalistic TTS TUI Reader with Word Highlighting
Requires: textual, pyperclip, kokoro-tts
Install: pip install textual pyperclip kokoro-tts
"""
from textual.app import App, ComposeResult
from textual.widgets import TextArea, Button, Footer, RichLog, Static
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets.text_area import Selection
from textual import work
import pyperclip
import threading
import time
import queue
import re
import bisect

from kokoro_tts import KokoroTTSProcessor


class StatusBar(Static):
    """Custom status bar with TTS state"""
    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #1a1a2e;
        color: #00ff9f;
        padding: 0 2;
        text-style: bold;
    }
    """
    
    status_text = reactive("Ready")
    
    def render(self) -> str:
        return self.status_text


class TTSReader(App):
    CSS = """
    Screen {
        background: #0f0f23;
    }

    StatusBar {
        border-bottom: heavy #00ff9f;
    }

    #main_container {
        height: 1fr;
        margin: 2 3;
        padding: 0;
    }

    #text_panel {
        height: 1fr;
        background: #1a1a2e;
        border: heavy #00d4ff;
        padding: 2;
    }

    TextArea {
        height: 1fr;
        background: #1a1a2e;
        color: #e0e0e0;
        border: none;
        padding: 1;
        scrollbar-gutter: stable;
        scrollbar-color: #00ff9f #1a1a2e;
    }

    TextArea:focus {
        border: none;
    }

    TextArea > .text-area--cursor {
        background: #ff00ff;
        color: #1a1a2e;
    }

    TextArea > .text-area--selection {
        background: #ff00ff 40%;
    }

    #log_container {
        height: 12;
        margin: 0 3 2 3;
        padding: 0;
    }

    #log_panel {
        height: 1fr;
        background: #1a1a2e;
        border: heavy #ff00ff;
        padding: 1 2;
    }

    RichLog {
        height: 1fr;
        background: transparent;
        color: #00ff9f;
        border: none;
        padding: 0;
    }

    #controls {
        height: auto;
        dock: bottom;
        background: #0f0f23;
        padding: 2 3 3 3;
        align: center middle;
    }

    #button_row {
        width: auto;
        height: auto;
        align: center middle;
    }

    Button {
        min-width: 14;
        height: 3;
        margin: 0 1;
        border: heavy #00d4ff;
        background: #1a1a2e;
        color: #00d4ff;
        text-style: bold;
    }

    Button:hover {
        background: #00d4ff 20%;
        color: #ffffff;
        border: heavy #00ff9f;
    }

    Button:disabled {
        opacity: 0.6;
        border: heavy #00d4ff;
        color: #00d4ff;
    }

    Footer {
        background: #1a1a2e;
        color: #00ff9f;
        border-top: heavy #00d4ff;
    }

    Footer > .footer--highlight {
        background: #ff00ff;
        color: #ffffff;
    }

    Footer > .footer--key {
        background: #00d4ff;
        color: #0f0f23;
    }

    /* Smooth transitions */
    Button {
        transition: background 100ms, border 100ms, color 100ms;
    }
    """

    BINDINGS = [
        Binding("ctrl+v", "paste", "Paste", show=True),
        Binding("ctrl+p", "toggle_play", "Play", show=True),
        Binding("ctrl+s", "stop_audio", "Stop", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    is_playing = reactive(False)
    tts_ready = reactive(False)

    def __init__(self, debug_mode=False):
        super().__init__()
        self.debug_mode = debug_mode
        self.tts = None
        self.original_text = ""
        self._playback_worker = None
        self._highlight_worker = None
        self._word_queue = queue.Queue()
        self._stop_highlighting = threading.Event()
        self._pending_play_after_ready = False
        self._word_spans = []
        self._word_span_pos = 0

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status")
        
        with Vertical(id="main_container"):
            with Container(id="text_panel"):
                yield TextArea(
                    "",
                    id="text_input",
                    soft_wrap=True,
                    language="text",
                    theme="css"
                )
        
        if self.debug_mode:
            with Vertical(id="log_container"):
                with Container(id="log_panel"):
                    yield RichLog(id="log", wrap=True, markup=True, auto_scroll=True)
        
        with Horizontal(id="controls"):
            with Horizontal(id="button_row"):
                yield Button("Paste", id="paste")
                yield Button("Play", id="play")
                yield Button("Stop", id="stop")
                yield Button("Quit", id="quit") 
        
        yield Footer()

    def on_mount(self):
        self.update_status("▶ INITIALIZING...")
        self.update_controls()
        self.log_message("[dim]>>> Initializing TTS engine...[/dim]")
        self._init_tts()

    @work(thread=True)
    def _init_tts(self):
        try:
            self.tts = KokoroTTSProcessor(stream_audio=True, setup_signals=False)
            self.tts_ready = True
            self.call_from_thread(self.update_status, "Ready")
            self.call_from_thread(self.log_message, "[green]>>> TTS engine initialized[/green]")

            if self._pending_play_after_ready:
                self._pending_play_after_ready = False
                self.call_from_thread(self.action_toggle_play)

            self.call_from_thread(self.update_controls)
        except Exception as e:
            self.call_from_thread(self.update_status, "Error")
            self.call_from_thread(self.log_message, f"[red]>>> TTS initialization failed: {e}[/red]")

    def update_status(self, text: str):
        try:
            status = self.query_one(StatusBar)
            status.status_text = text
        except Exception:
            pass

    # --- Actions ---
    def action_paste(self):
        try:
            text = pyperclip.paste()
            if text:
                self.query_one("#text_input", TextArea).text = text
                self.log_message("[green]>>> Text pasted from clipboard[/green]")
                self.update_status("Text loaded")
        except Exception as e:
            self.log_message(f"[red]>>> Paste failed: {e}[/red]")

    def action_toggle_play(self):
        textarea = self.query_one("#text_input", TextArea)
        text = textarea.text
        if text.strip():
            play_btn = self.query_one("#play", Button)
            stop_btn = self.query_one("#stop", Button)
            if self.is_playing:
                self.stop_audio()
            else:
                if not self.tts_ready:
                    self.log_message("[cyan]>>> TTS loading... will auto-play[/cyan]")
                    self.update_status("Loading...")
                    self._pending_play_after_ready = True
                    play_btn.disabled = True
                    stop_btn.disabled = True
                else:
                    self.play_audio()

    def action_stop_audio(self):
        self.stop_audio()

    def action_quit(self):
        try:
            self.update_status("Exiting...")
        except Exception:
            pass
        self._ensure_tts_stopped()
        self.exit()  # cleanly exits the Textual app

    def on_button_pressed(self, event: Button.Pressed):
        mapping = {
            "paste": self.action_paste,
            "play": self.action_toggle_play,
            "stop": self.action_stop_audio,
            "quit": self.action_quit, 
        }
        action = mapping.get(event.button.id)
        if action:
            action()

    # --- Word span mapping ---
    @staticmethod
    def _normalize_token(s: str) -> str:
        return re.sub(r"[^A-Za-z0-9']+", "", s).lower()

    @staticmethod
    def _line_starts(text: str):
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        return starts

    def _build_word_spans(self, text: str):
        spans = []
        line_starts = self._line_starts(text)
        for m in re.finditer(r"\S+", text):
            abs_start, abs_end = m.start(), m.end()
            row = bisect.bisect_right(line_starts, abs_start) - 1
            start_col = abs_start - line_starts[row]
            end_col = abs_end - line_starts[row]
            spans.append({
                "token": m.group(),
                "row": row,
                "start_col": start_col,
                "end_col": end_col,
            })
        return spans

    # --- Playback + Highlight ---
    def play_audio(self):
        if not self.tts_ready:
            self.log_message("[cyan]>>> TTS is still loading[/cyan]")
            return

        textarea = self.query_one("#text_input", TextArea)
        text = textarea.text
        if not text.strip():
            self.log_message("[cyan]>>> No text to read[/cyan]")
            return

        self._ensure_tts_stopped()
        self._word_spans = self._build_word_spans(text)
        self._word_span_pos = 0
        self.is_playing = True
        self._stop_highlighting.clear()

        while not self._word_queue.empty():
            try:
                self._word_queue.get_nowait()
            except queue.Empty:
                break

        textarea.focus()
        self.update_status("Playing...")

        self._highlight_worker = threading.Thread(target=self._highlight_loop, daemon=True)
        self._highlight_worker.start()

        self._playback_worker = threading.Thread(
            target=self._tts_playback_thread, args=(text,), daemon=True
        )
        self._playback_worker.start()

    def _highlight_loop(self):
        prev_end_time = 0.0
        while not self._stop_highlighting.is_set():
            try:
                item = self._word_queue.get(timeout=0.1)
                if item is None:
                    break

                row, start_col, end_col, start_time, end_time = (
                    item["row"],
                    item["start_col"],
                    item["end_col"],
                    item["start_time"],
                    item["end_time"],
                )

                self.call_from_thread(self._set_selection, row, start_col, end_col)

                if prev_end_time > end_time:
                    prev_end_time = -0.2 # add buffer when next audio plays
                duration = max(0.0, end_time - prev_end_time)
                prev_end_time = end_time

                time.sleep(duration)

            except queue.Empty:
                continue
            except Exception as e:
                self.call_from_thread(lambda: self.log_message(f"[red]>>> Highlight error: {e}[/red]"))
                break

    MATCH_WINDOW = 12

    def _set_selection(self, row: int, start_col: int, end_col: int):
        try:
            textarea = self.query_one("#text_input", TextArea)
            textarea.selection = Selection(start=(row, start_col), end=(row, end_col))
            textarea.focus()
            textarea.scroll_to(y=row, immediate=True)
        except Exception as e:
            self.log_message(f"[red]>>> Selection error: {e}[/red]")

    def _tts_playback_thread(self, text: str):
        try:
            def word_cb(word_datas, audio_duration):
                self.log_message(word_datas)
                for wd_index, wd in enumerate(word_datas):
                    tts_word = wd.get("word", "")
                    if not tts_word or not any(ch.isalnum() for ch in tts_word):
                        continue

                    start_index = self._word_span_pos
                    end_index = min(start_index + 1, len(self._word_spans))

                    match_idx = None
                    for i in range(start_index, end_index):
                        if self._word_spans[i]["token"] == tts_word:
                            match_idx = i
                            break

                    if match_idx is None:
                        if self._word_span_pos < len(self._word_spans):
                            match_idx = self._word_span_pos
                        else:
                            continue

                    span = self._word_spans[match_idx]
                    self._word_span_pos = match_idx + 1

                    start_time = wd.get("start_time", 0.0)
                    end_time = wd.get("end_time", 0.0)
                    if start_time == None and end_time == None:
                        if wd_index + 1 == len(word_datas):
                            start_time = word_datas[wd_index - 1]["end_time"]
                            end_time = audio_duration
                        else:
                            start_time = word_datas[wd_index - 1]["end_time"]
                            end_time = word_datas[wd_index + 1]["start_time"]

                    self._word_queue.put(
                        {
                            "word": span["token"],
                            "row": span["row"],
                            "start_col": span["start_col"],
                            "end_col": span["end_col"],
                            "start_time": float(start_time) if start_time is not None else 0.0,
                            "end_time": float(end_time) if end_time is not None else 0.0,
                        }
                    )

            self.tts.word_callback = word_cb
            self.tts.start_audio_streaming()
            self.tts.generate_audio_files(text, self.tts.voices[2], self.tts.default_speed)
            self._word_queue.put(None)
            self.tts.wait_for_audio_streaming_complete()
            self.tts.stop_audio_streaming()
            self.call_from_thread(self.update_status, "Completed")
            self.call_from_thread(lambda: self.log_message("[green]>>> Playback complete[/green]"))
        except Exception as e:
            self.call_from_thread(lambda: self.log_message(f"[red]>>> Playback error: {e}[/red]"))
        finally:
            self.tts.word_callback = None
            self._stop_highlighting.set()
            self.is_playing = False
            self.call_from_thread(self._cleanup_playback)

    def _ensure_tts_stopped(self):
        if self.tts:
            try:
                if hasattr(self.tts, "is_streaming") and self.tts.is_streaming:
                    if hasattr(self.tts, "force_stop_streaming"):
                        self.tts.force_stop_streaming()
                if hasattr(self.tts, "audio_queue"):
                    while not self.tts.audio_queue.empty():
                        try:
                            self.tts.audio_queue.get_nowait()
                        except Exception:
                            break
                self.tts.is_streaming = False
            except Exception as e:
                self.log_message(f"[cyan]>>> Cleanup warning: {e}[/cyan]")

        self._stop_highlighting.set()
        if self._highlight_worker and self._highlight_worker.is_alive():
            self._highlight_worker.join(timeout=0.2)
        if self._playback_worker and self._playback_worker.is_alive():
            self._playback_worker.join(timeout=0.2)
        self.is_playing = False

    def stop_audio(self):
        if not self.is_playing:
            return
        self.is_playing = False
        self._stop_highlighting.set()
        self._ensure_tts_stopped()
        self._cleanup_playback()
        self.update_status("Stopped")
        self.log_message("[red]>>> Playback stopped[/red]")

    def _cleanup_playback(self):
        textarea = self.query_one("#text_input", TextArea)
        textarea.selection = Selection()
        self.update_controls()

    # --- UI ---
    def log_message(self, message):
        if not self.debug_mode:
            return
        try:
            self.query_one("#log", RichLog).write(message)
        except Exception:
            pass

    def watch_is_playing(self, is_playing):
        self.update_controls()
        play_btn = self.query_one("#play", Button)
        play_btn.label = "Play"

    def update_controls(self):
        try:
            play_btn = self.query_one("#play", Button)
            stop_btn = self.query_one("#stop", Button)
            play_btn.disabled = self.is_playing
            stop_btn.disabled = not self.is_playing
        except Exception:
            pass


def main():
    import sys
    debug_mode = "--debug" in sys.argv
    TTSReader(debug_mode=debug_mode).run(headless=False)

if __name__ == "__main__":
    main()