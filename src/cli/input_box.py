"""Bordered, multiline ``prompt_toolkit`` input box (Claude-style prompt).

Key bindings are attached directly to the ``BufferControl``: bindings on a
focused control take precedence over the default insert-mode bindings, so
``Enter`` reliably submits and ``Esc+Enter`` reliably inserts a newline.
"""
from __future__ import annotations

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.widgets import Frame

from ..theme import ACCENT, MUTED, SUBTLE


PT_STYLE = PTStyle.from_dict(
    {
        "frame.border": f"fg:{ACCENT}",
        "frame.label": f"fg:{ACCENT} bold",
        "input.prompt": f"fg:{ACCENT} bold",
        "toolbar": f"fg:{MUTED}",
        "toolbar.key": f"fg:{ACCENT} bold",
        "toolbar.sep": f"fg:{SUBTLE}",
    }
)


def _prompt_input_box(thread_id: str, model: str, provider: str | None = None) -> str | None:
    """Render the bordered, multiline input box and return the submitted text.

    Returns None if the user cancels (Ctrl+C / Ctrl+D on empty buffer).
    Returns "" (empty string) if the user submits an empty buffer (treated as no-op by caller).
    """
    buffer = Buffer(multiline=True)

    # Bindings registered directly on the BufferControl take precedence over
    # the default insert-mode "Enter inserts newline" binding when this
    # control has focus, which is exactly what we need for "Enter sends".
    control_kb = KeyBindings()

    @control_kb.add("enter")
    def _submit(event) -> None:
        event.app.exit(result=buffer.text)

    @control_kb.add("escape", "enter")
    def _newline(event) -> None:
        buffer.insert_text("\n")

    @control_kb.add("c-j")  # Some terminals deliver Shift+Enter as Ctrl+J
    def _newline_cj(event) -> None:
        buffer.insert_text("\n")

    @control_kb.add("c-c")
    def _cancel(event) -> None:
        if buffer.text:
            buffer.reset()
        else:
            event.app.exit(result=None)

    @control_kb.add("c-d")
    def _eof(event) -> None:
        if not buffer.text:
            event.app.exit(result=None)

    control = BufferControl(
        buffer=buffer,
        key_bindings=control_kb,
        input_processors=[BeforeInput([("class:input.prompt", "▸ ")])],
        focusable=True,
    )

    input_window = Window(
        content=control,
        height=D(min=1, max=12),
        wrap_lines=True,
        always_hide_cursor=False,
    )

    def get_toolbar():
        return [
            ("class:toolbar.key", "  ⏎ "),
            ("class:toolbar", "send  "),
            ("class:toolbar.sep", "·  "),
            ("class:toolbar.key", "esc+⏎ "),
            ("class:toolbar", "newline  "),
            ("class:toolbar.sep", "·  "),
            ("class:toolbar.key", "/help "),
            ("class:toolbar", "commands  "),
            ("class:toolbar.sep", "·  "),
            ("class:toolbar.key", "ctrl+c "),
            ("class:toolbar", "exit  "),
            ("class:toolbar.sep", "·  "),
            ("class:toolbar", "thread "),
            ("class:toolbar.key", f"{thread_id}"),
            (
                "class:toolbar",
                f"   {provider + ' · ' if provider else ''}{model}",
            ),
        ]

    toolbar = Window(
        content=FormattedTextControl(get_toolbar),
        height=1,
        style="class:toolbar",
    )

    root = HSplit(
        [
            Frame(input_window, style="class:frame"),
            toolbar,
        ]
    )

    app = Application(
        layout=Layout(root, focused_element=input_window),
        style=PT_STYLE,
        editing_mode=EditingMode.EMACS,
        full_screen=False,
        mouse_support=False,
        erase_when_done=False,
    )

    try:
        # Allow background worker logs to render while the input box is active.
        with patch_stdout(raw=True):
            return app.run()
    except (KeyboardInterrupt, EOFError):
        return None
