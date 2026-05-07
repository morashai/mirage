"""Interactive terminal form for provider, model, API key, and base URL."""
from __future__ import annotations

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension as D
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.processors import BeforeInput, PasswordProcessor
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.widgets import Box, Button, Frame, Label, RadioList

from ..config_store import MirageConfig, mask_secret, resolve_api_key, resolve_base_url, save_config
from ..llm.catalog import PROVIDERS, list_models_for_provider
from ..theme import ACCENT, MUTED, SUBTLE


PT_FORM_STYLE = PTStyle.from_dict(
    {
        "frame.border": f"fg:{ACCENT}",
        "frame.label": f"fg:{ACCENT} bold",
        "input.prompt": f"fg:{ACCENT} bold",
        "toolbar": f"fg:{MUTED}",
        "toolbar.key": f"fg:{ACCENT} bold",
        "toolbar.sep": f"fg:{SUBTLE}",
        "label": f"fg:{MUTED}",
        "radio-selected": f"fg:{ACCENT} bold",
    }
)


class ModelFormResult(dict):
    """Mapping with keys: provider, model, api_key, base_url."""

    pass


class _CatalogCompleter(Completer):
    def __init__(self, get_provider):
        self._get_provider = get_provider

    def get_completions(self, document: Document, complete_event):
        word = document.get_word_before_cursor().lower()
        for m in list_models_for_provider(self._get_provider()):
            if not word:
                yield Completion(m)
            elif m.lower().startswith(word):
                yield Completion(m, start_position=-len(word))


def run_model_form(
    cfg: MirageConfig,
    *,
    initial_provider: str | None = None,
    initial_model: str | None = None,
    title: str = "Model & API configuration",
) -> ModelFormResult | None:
    """Show a bordered form; return submitted values or ``None`` if cancelled."""
    app_ref: list[Application | None] = [None]

    start_prov = initial_provider if initial_provider in PROVIDERS else cfg.default_provider
    radio = RadioList([(p, p) for p in PROVIDERS], default=start_prov)

    def current_provider() -> str:
        return str(radio.current_value)

    ps = cfg.provider_settings(start_prov)
    env_fallback = resolve_api_key(cfg, start_prov)

    catalog_completer = _CatalogCompleter(current_provider)
    # Some prompt_toolkit runtimes trigger async completion without an event
    # loop when complete_while_typing=True. Keep completion manual.
    model_buf = Buffer(completer=catalog_completer, complete_while_typing=False)
    model_buf.insert_text(initial_model or cfg.default_model or "")

    existing_key = ps.api_key or env_fallback or ""
    key_placeholder = (
        f"(stored {mask_secret(existing_key)}) — type to replace; leave empty to keep"
        if existing_key
        else "(not set — paste key)"
    )

    key_buf = Buffer()
    url_buf = Buffer()
    if ps.base_url:
        url_buf.insert_text(ps.base_url)

    result_holder: list[ModelFormResult | None] = [None]

    model_control = BufferControl(
        buffer=model_buf,
        input_processors=[BeforeInput([("class:input.prompt", " ")])],
        focusable=True,
    )
    key_control = BufferControl(
        buffer=key_buf,
        input_processors=[
            PasswordProcessor(),
            BeforeInput([("class:input.prompt", " ")]),
        ],
        focusable=True,
    )
    url_control = BufferControl(
        buffer=url_buf,
        input_processors=[BeforeInput([("class:input.prompt", " ")])],
        focusable=True,
    )

    model_window = Window(content=model_control, height=D(max=4), wrap_lines=False)
    key_window = Window(content=key_control, height=D(max=3), wrap_lines=False)
    url_window = Window(content=url_control, height=D(max=3), wrap_lines=False)

    hint = Window(
        FormattedTextControl(lambda: [("class:toolbar", key_placeholder)]),
        height=D.exact(1),
    )

    def submit() -> None:
        prov = current_provider()
        model_text = model_buf.text.strip()
        key_text = key_buf.text.strip()
        url_text = url_buf.text.strip()

        st = cfg.provider_settings(prov)
        prev_key = st.api_key
        prev_url = st.base_url

        cfg.default_provider = prov
        if model_text:
            cfg.default_model = model_text

        if key_text:
            st.api_key = key_text
        # leaving empty keeps file/env-backed key unchanged

        if url_text.strip():
            st.base_url = url_text.strip()
        else:
            st.base_url = None

        save_config(cfg)

        merged_key = key_text or prev_key or resolve_api_key(cfg, prov)
        merged_url = resolve_base_url(cfg, prov)

        result_holder[0] = ModelFormResult(
            provider=prov,
            model=model_text or cfg.default_model,
            api_key=merged_key,
            base_url=merged_url,
        )
        if app_ref[0] is not None:
            app_ref[0].exit()

    def cancel() -> None:
        result_holder[0] = None
        if app_ref[0] is not None:
            app_ref[0].exit()

    save_btn = Button(text=" Save ", handler=submit)
    cancel_btn = Button(text=" Cancel ", handler=cancel)

    button_row = VSplit([save_btn, Window(width=D.exact(2)), cancel_btn], padding=0)

    body = HSplit(
        [
            Label("Provider", style="class:label"),
            radio,
            Label("Model", style="class:label"),
            model_window,
            Label("API key", style="class:label"),
            hint,
            key_window,
            Label("Base URL (optional)", style="class:label"),
            url_window,
            Window(height=D.exact(1)),
            button_row,
            Window(
                FormattedTextControl(
                    [
                        (
                            "class:toolbar",
                            "Tab / Shift+Tab navigate · Ctrl+Space model suggestions · Esc cancel · Enter on Save",
                        ),
                    ]
                ),
                height=D.exact(1),
            ),
        ]
    )

    root = Frame(Box(body), title=title, style="class:frame")

    nav_kb = KeyBindings()

    focus_order = [radio, model_window, key_window, url_window, save_btn, cancel_btn]

    def _focus_idx(app: Application) -> int:
        cur = app.layout.current_window
        try:
            return focus_order.index(cur)
        except ValueError:
            return 0

    @nav_kb.add("tab")
    def _tab(event) -> None:
        app = event.app
        i = _focus_idx(app)
        app.layout.focus(focus_order[(i + 1) % len(focus_order)])

    @nav_kb.add("s-tab")
    def _stab(event) -> None:
        app = event.app
        i = _focus_idx(app)
        app.layout.focus(focus_order[(i - 1) % len(focus_order)])

    @nav_kb.add("escape")
    def _esc(event) -> None:
        cancel()

    @nav_kb.add("c-space")
    def _complete_model(event) -> None:
        if event.app.layout.current_window == model_window:
            model_buf.start_completion(select_first=False)

    app = Application(
        layout=Layout(root, focused_element=model_window),
        style=PT_FORM_STYLE,
        editing_mode=EditingMode.EMACS,
        full_screen=False,
        mouse_support=True,
        erase_when_done=False,
        key_bindings=nav_kb,
    )
    app_ref[0] = app

    try:
        app.run()
    except (KeyboardInterrupt, EOFError):
        return None

    return result_holder[0]
