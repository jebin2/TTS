"""
Minimalistic TTS TUI Reader with Word Highlighting
Requires: textual, pyperclip, kokoro-tts
Install: pip install textual pyperclip kokoro-tts
"""
from textual.app import App, ComposeResult
from textual.widgets import TextArea, Button, Footer, RichLog
from textual.containers import Horizontal, Vertical
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


class TTSReader(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #main_container {
        height: 3fr;
        border: solid $primary;
        padding: 1;
    }

    TextArea {
        height: 1fr;
        border: solid $secondary;
        padding: 1;
    }

    #log_container {
        height: 2fr;
        border: solid $accent;
        padding: 1;
    }

    RichLog {
        height: 100%;
        overflow-y: auto;
    }

    #controls {
        height: 3;
        dock: bottom;
        background: $surface;
        padding: 0 1;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+v", "paste", "Paste"),
        Binding("ctrl+p", "toggle_play", "Play/Pause"),
        Binding("ctrl+s", "stop_audio", "Stop"),
        Binding("q", "quit", "Quit"),
    ]

    is_playing = reactive(False)
    tts_ready = reactive(False)

    def __init__(self):
        super().__init__()
        self.tts = None
        self.original_text = ""
        self._playback_worker = None
        self._highlight_worker = None
        self._word_queue = queue.Queue()
        self._stop_highlighting = threading.Event()

        # Token span map over the current TextArea buffer:
        # list of dicts: { "token": str, "row": int, "start_col": int, "end_col": int }
        self._word_spans = []
        self._word_span_pos = 0  # advancing pointer while matching TTS words to text spans

    def compose(self) -> ComposeResult:
        with Vertical(id="main_container"):
            # Regular TextArea with soft wrap
            yield TextArea(
                "", 
                id="text_input", 
                soft_wrap=True,      # enable wrapping
                language="text"      # keep plain text syntax behaviors
            )
        with Vertical(id="log_container"):
            yield RichLog(id="log", wrap=True, markup=True, auto_scroll=True)
        with Horizontal(id="controls"):
            yield Button("Paste [Ctrl+V]", id="paste", variant="success")
            yield Button("Play [Ctrl+P]", id="play", variant="primary")
            yield Button("Stop [Ctrl+S]", id="stop", variant="error")
        yield Footer()

    def on_mount(self):
        self.update_controls()
        self.log_message("[dim]Initializing TTS...[/dim]")
        self._init_tts()

    @work(thread=True)
    def _init_tts(self):
        try:
            self.tts = KokoroTTSProcessor(stream_audio=True, setup_signals=False)
            self.tts_ready = True
            self.call_from_thread(self.log_message, "[green]✓ TTS Ready[/green]")
        except Exception as e:
            self.call_from_thread(self.log_message, f"[red]TTS Init Error: {e}[/red]")

    # --- Actions ---
    def action_paste(self):
        try:
            text = pyperclip.paste()
            if text:
                self.query_one("#text_input", TextArea).text = text
                self.log_message("[green]Text pasted successfully[/green]")
        except Exception as e:
            self.log_message(f"[red]Paste failed: {e}[/red]")

    def action_toggle_play(self):
        if self.is_playing:
            self.stop_audio()
        else:
            self.play_audio()

    def action_stop_audio(self):
        self.stop_audio()

    def on_button_pressed(self, event: Button.Pressed):
        mapping = {
            "paste": self.action_paste,
            "play": self.play_audio,
            "stop": self.stop_audio,
        }
        action = mapping.get(event.button.id)
        if action:
            action()

    # --- Word span mapping ---
    @staticmethod
    def _normalize_token(s: str) -> str:
        # Keep alnum and apostrophes (typical TTS tokenization), lowercase
        return re.sub(r"[^A-Za-z0-9']+", "", s).lower()

    @staticmethod
    def _line_starts(text: str):
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        return starts

    def _build_word_spans(self, text: str):
        """
        Build a sequential list of word-like token spans over the full document,
        with precise (row, start_col, end_col) coordinates for each token.
        """
        spans = []
        line_starts = self._line_starts(text)
        # Regex for word-like tokens (includes contractions)
        for m in re.finditer(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text):
            abs_start, abs_end = m.start(), m.end()
            # Map absolute index -> (row, col)
            row = bisect.bisect_right(line_starts, abs_start) - 1
            start_col = abs_start - line_starts[row]
            end_col = abs_end - line_starts[row]
            spans.append(
                {
                    "token": self._normalize_token(m.group()),
                    "row": row,
                    "start_col": start_col,
                    "end_col": end_col,
                }
            )
        return spans

    # --- Playback + Highlight ---
    def play_audio(self):
        if not self.tts_ready:
            self.log_message("[yellow]TTS is still loading[/yellow]")
            return

        textarea = self.query_one("#text_input", TextArea)
        text = textarea.text
        if not text.strip():
            self.log_message("[yellow]No text to read[/yellow]")
            return

        # Ensure clean state
        self._ensure_tts_stopped()

        # Precompute word spans for the current text
        self._word_spans = self._build_word_spans(text)
        self._word_span_pos = 0

        self.is_playing = True
        self._stop_highlighting.clear()

        # Drain any stale queue items
        while not self._word_queue.empty():
            try:
                self._word_queue.get_nowait()
            except queue.Empty:
                break

        # Ensure the TextArea has focus so the selection is visible
        textarea.focus()

        # Start workers
        self._highlight_worker = threading.Thread(target=self._highlight_loop, daemon=True)
        self._highlight_worker.start()

        self._playback_worker = threading.Thread(
            target=self._tts_playback_thread, args=(text,), daemon=True
        )
        self._playback_worker.start()

    def _highlight_loop(self):
        """
        Process queued word selections and highlight them for the duration
        between the previous word's end_time and current word's end_time.
        """
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

                # Apply selection in the main thread
                self.call_from_thread(self._set_selection, row, start_col, end_col)

                # Duration = current_end_time - previous_end_time
                duration = max(0.0, end_time - prev_end_time)
                prev_end_time = end_time

                time.sleep(duration)

            except queue.Empty:
                continue
            except Exception as e:
                self.call_from_thread(lambda: self.log_message(f"[red]Highlight error: {e}[/red]"))
                break


    MATCH_WINDOW = 12  # tokens to look ahead for a match
    def _set_selection(self, row: int, start_col: int, end_col: int):
        try:
            textarea = self.query_one("#text_input", TextArea)
            # Move caret to end of selection (Textual uses Selection.end as caret)
            textarea.selection = Selection(start=(row, start_col), end=(row, end_col))
            # Ensure caret is visible across versions
            textarea.focus()
            # Scroll the line into view (immediate to avoid animation lag)
            textarea.scroll_to(y=row, immediate=True)
        except Exception as e:
            self.log_message(f"[red]Selection error: {e}[/red]")

    def _tts_playback_thread(self, text: str):
        try:
            # Match Kokoro's per-word callback to our text spans in order
            def word_cb(word_datas):
                for wd in word_datas:
                    tts_word = self._normalize_token(str(wd.get("word", "")))
                    if not tts_word:
                        continue

                    start_index = self._word_span_pos
                    end_index = min(start_index + self.MATCH_WINDOW, len(self._word_spans))

                    match_idx = None
                    # Bounded forward window
                    for i in range(start_index, end_index):
                        if self._word_spans[i]["token"] == tts_word:
                            match_idx = i
                            break

                    if match_idx is None:
                        # Conservative resync: advance one span if possible to avoid large jumps
                        if self._word_span_pos < len(self._word_spans):
                            match_idx = self._word_span_pos
                        else:
                            continue  # out of spans

                    span = self._word_spans[match_idx]
                    self._word_span_pos = match_idx + 1

                    self._word_queue.put(
                        {
                            "row": span["row"],
                            "start_col": span["start_col"],
                            "end_col": span["end_col"],
                            "start_time": float(wd.get("start_time", 0.0)),
                            "end_time": float(wd.get("end_time", 0.0)),
                        }
                    )

            self.tts.word_callback = word_cb
            self.tts.start_audio_streaming()
            voice = self.tts.voices[self.tts.default_voice_index]
            speed = self.tts.default_speed
            self.tts.generate_audio_files(text, voice, speed)
            self._word_queue.put(None)
            self.tts.wait_for_audio_streaming_complete()
            self.tts.stop_audio_streaming()
            self.call_from_thread(lambda: self.log_message("[green]✓ Playback complete[/green]"))
        except Exception as e:
            self.call_from_thread(lambda: self.log_message(f"[red]Playback error: {e}[/red]"))
        finally:
            self.tts.word_callback = None
            self._stop_highlighting.set()
            self.is_playing = False
            self.call_from_thread(self._cleanup_playback)

    def _ensure_tts_stopped(self):
        """
        Stop any ongoing TTS playback, clear queues, reset state.
        """
        if self.tts:
            try:
                if hasattr(self.tts, "is_streaming") and self.tts.is_streaming:
                    # Force immediate stop if available
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
                self.log_message(f"[yellow]Cleanup warning: {e}[/yellow]")

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
        self.log_message("[red]⏹ Stopped[/red]")

    def _cleanup_playback(self):
        textarea = self.query_one("#text_input", TextArea)
        textarea.selection = Selection()  # clear selection
        self.update_controls()

    # --- UI ---
    def log_message(self, message):
        try:
            self.query_one("#log", RichLog).write(message)
        except Exception:
            pass

    def watch_is_playing(self, is_playing):
        self.update_controls()

    def update_controls(self):
        try:
            play_btn = self.query_one("#play", Button)
            stop_btn = self.query_one("#stop", Button)
            play_btn.disabled = self.is_playing
            stop_btn.disabled = not self.is_playing
        except Exception:
            pass


def main():
    TTSReader().run()


if __name__ == "__main__":
    main()
