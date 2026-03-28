import json
import os
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import gradio as gr
import main

APP_DIR = Path(__file__).resolve().parent
SAVED_SCENES_DIR = APP_DIR / "saved_scenes"
SAVED_SCENES_DIR.mkdir(exist_ok=True)

EXAMPLE_COMMANDS = [
    "irish flag",
    "sunset wash",
    "calm ocean static wash",
    "american police lights",
    "flame",
    "black, black, black, green. fast chase",
    "white strobe medium speed"
]

MAX_HISTORY = 10
MAX_SAVED_ROWS = 24

_state_lock = threading.Lock()
_stop_event = threading.Event()
_effect_thread = None


def gui_check_for_exit_key():
    if _stop_event.is_set():
        try:
            main.blackout()
        except Exception:
            pass
        return True
    return False


# Minimal integration point: reuse main.py functions, but swap terminal key polling
# for a GUI-controlled stop event.
main.check_for_exit_key = gui_check_for_exit_key


def speed_to_label(speed: str) -> str:
    return speed.capitalize()


def mode_to_label(mode: str) -> str:
    return mode.capitalize()


def fixtures_to_serialisable(fixtures):
    return [{"r": r, "g": g, "b": b, "w": w} for r, g, b, w in fixtures]


def fixtures_from_serialisable(fixtures_data):
    return [(f["r"], f["g"], f["b"], f["w"]) for f in fixtures_data]


def make_scene_dict(request_text: str, colours: str, mode: str, speed: str, fixtures):
    return {
        "request": request_text,
        "colours": colours,
        "mode": mode,
        "speed": speed,
        "fixtures": fixtures_to_serialisable(fixtures),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def scene_summary_html(scene: dict[str, Any], title: str | None = None) -> str:
    title_html = ""
    if title:
        title_html = f"<div class='scene-title'>{title}</div>"

    return f"""
    <div class='scene-card'>
        {title_html}
        <div class='scene-line'><span class='scene-label'>Request</span><span>{scene['request']}</span></div>
        <div class='scene-line'><span class='scene-label'>Colours</span><span>{scene['colours']}</span></div>
        <div class='scene-line scene-inline'>
            <span class='scene-pill'>Mode: {mode_to_label(scene['mode'])}</span>
            <span class='scene-pill'>Speed: {speed_to_label(scene['speed'])}</span>
        </div>
        <div class='scene-time'>{scene.get('timestamp', '')}</div>
    </div>
    """


def empty_scene_html(message: str) -> str:
    return f"<div class='empty-card'>{message}</div>"


def build_initial_state():
    return {
        "current_scene": None,
        "history": [],
        "saved_scenes": load_saved_scenes(),
        "status": "Ready.",
    }


def load_saved_scenes():
    scenes = []
    for path in sorted(SAVED_SCENES_DIR.glob("scene*.json"), key=lambda p: p.name.lower()):
        try:
            with open(path, "r", encoding="utf-8") as f:
                scene = json.load(f)
            scene["file_path"] = str(path)
            scenes.append(scene)
        except (OSError, json.JSONDecodeError):
            continue
    return scenes


def next_scene_path() -> Path:
    i = 1
    while True:
        candidate = SAVED_SCENES_DIR / f"scene{i}.json"
        if not candidate.exists():
            return candidate
        i += 1


def save_scene_to_disk(scene: dict[str, Any]) -> dict[str, Any]:
    path = next_scene_path()
    scene_to_save = deepcopy(scene)
    scene_to_save["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scene_to_save, f, indent=2)
    scene_to_save["file_path"] = str(path)
    return scene_to_save


def stop_current_effect(send_blackout: bool = True):
    global _effect_thread

    _stop_event.set()

    if _effect_thread is not None and _effect_thread.is_alive():
        _effect_thread.join(timeout=1.0)

    _effect_thread = None

    if send_blackout:
        try:
            main.blackout()
        except Exception:
            pass

    _stop_event.clear()


def play_scene(scene: dict[str, Any]):
    global _effect_thread

    stop_current_effect(send_blackout=True)

    fixtures = fixtures_from_serialisable(scene["fixtures"])
    delay = main.speed_to_delay(scene["speed"])

    if scene["mode"] == "static":
        main.colour_static(fixtures, delay)
    else:
        _effect_thread = threading.Thread(
            target=main.mode_choice,
            args=(scene["mode"], fixtures, delay),
            daemon=True,
        )
        _effect_thread.start()


def run_prompt(user_prompt: str, state: dict[str, Any]):
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        state["status"] = "Enter a lighting command first."
        return state

    stop_current_effect(send_blackout=True)

    colour_reply = main.ask_llm_colour_names(user_prompt)
    if colour_reply is None:
        state["status"] = "Could not reach the LLM for colours."
        return state

    colours = main.parse_colour_names(colour_reply)

    json_reply = main.ask_llm_json(colours)
    if json_reply is None:
        state["status"] = "Could not reach the LLM for DMX values."
        return state

    fixtures = main.parse_json_output(json_reply)

    mode_speed_reply = main.ask_llm_mode_speed(user_prompt)
    if mode_speed_reply is None:
        mode = "static"
        speed = "medium"
    else:
        mode, speed = main.parse_mode_speed(mode_speed_reply)

    scene = make_scene_dict(user_prompt, colours, mode, speed, fixtures)
    play_scene(scene)

    state["current_scene"] = scene
    state["history"] = [scene] + state["history"][: MAX_HISTORY - 1]
    state["status"] = "Scene sent to fixtures."
    return state


def replay_history(index: int, state: dict[str, Any]):
    if index >= len(state["history"]):
        return state

    scene = deepcopy(state["history"][index])
    play_scene(scene)
    state["current_scene"] = scene
    state["status"] = "History scene replayed."
    return state


def replay_saved(index: int, state: dict[str, Any]):
    if index >= len(state["saved_scenes"]):
        return state

    scene = deepcopy(state["saved_scenes"][index])
    play_scene(scene)
    state["current_scene"] = scene
    state["status"] = "Saved scene replayed."
    return state


def save_current_scene(state: dict[str, Any]):
    scene = state.get("current_scene")
    if not scene:
        state["status"] = "No current scene to save."
        return state

    saved_scene = save_scene_to_disk(scene)
    state["saved_scenes"] = load_saved_scenes()
    state["status"] = f"Saved current scene to {Path(saved_scene['file_path']).name}."
    return state


def save_history_scene(index: int, state: dict[str, Any]):
    if index >= len(state["history"]):
        return state

    scene = state["history"][index]
    saved_scene = save_scene_to_disk(scene)
    state["saved_scenes"] = load_saved_scenes()
    state["status"] = f"Saved history scene to {Path(saved_scene['file_path']).name}."
    return state


def delete_saved_scene(index: int, state: dict[str, Any]):
    if index >= len(state["saved_scenes"]):
        return state

    scene = state["saved_scenes"][index]
    file_path = scene.get("file_path")
    if file_path:
        try:
            os.remove(file_path)
        except OSError:
            pass

    state["saved_scenes"] = load_saved_scenes()
    state["status"] = "Saved scene deleted."
    return state


def stop_and_blackout(state: dict[str, Any]):
    stop_current_effect(send_blackout=True)
    state["status"] = "Stopped current effect and sent blackout."
    return state


CURRENT_HTML = gr.HTML()
STATUS_MD = gr.Markdown()


def render_ui(state: dict[str, Any]):
    current_scene = state.get("current_scene")
    current_html = (
        scene_summary_html(current_scene, "Currently running")
        if current_scene
        else empty_scene_html("No scene is currently running.")
    )

    updates = [current_html, f"**Status:** {state.get('status', 'Ready.')}\n"]

    history = state.get("history", [])
    for i in range(MAX_HISTORY):
        if i < len(history):
            scene = history[i]
            updates.extend([
                gr.update(value=scene_summary_html(scene, f"Latest scene {i + 1}"), visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
            ])
        else:
            updates.extend([
                gr.update(value="", visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            ])

    saved = state.get("saved_scenes", [])
    for i in range(MAX_SAVED_ROWS):
        if i < len(saved):
            scene = saved[i]
            title = Path(scene.get("file_path", f"scene{i+1}.json")).name
            updates.extend([
                gr.update(value=scene_summary_html(scene, title), visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
            ])
        else:
            updates.extend([
                gr.update(value="", visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            ])

    return [state] + updates


CSS = """
.gradio-container {
    max-width: 1200px !important;
}
.hero {
    padding: 14px 18px;
    border-radius: 22px;
    background: linear-gradient(135deg, rgba(92,99,255,.12), rgba(0,194,255,.10));
    border: 1px solid rgba(255,255,255,.08);
    margin-bottom: 10px;
}
.scene-card, .empty-card {
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 18px;
    padding: 14px 16px;
    background: rgba(255,255,255,.03);
}
.scene-title {
    font-size: 1.02rem;
    font-weight: 700;
    margin-bottom: 10px;
}
.scene-line {
    display: flex;
    gap: 10px;
    margin-bottom: 8px;
    align-items: flex-start;
}
.scene-inline {
    gap: 8px;
    flex-wrap: wrap;
}
.scene-label {
    min-width: 72px;
    font-weight: 600;
    opacity: .85;
}
.scene-pill {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    background: rgba(255,255,255,.07);
    font-size: .95rem;
}
.scene-time {
    opacity: .66;
    font-size: .9rem;
    margin-top: 6px;
}
.section-title {
    margin: 14px 0 6px;
    font-size: 1.1rem;
    font-weight: 700;
}
"""


with gr.Blocks() as demo:
    app_state = gr.State(build_initial_state())

    gr.HTML(
        """
        <div class='hero'>
            <h1 style='margin:0;'>neuraLumaDMX</h1>
            <p style='margin:.45rem 0 0 0; opacity:.82;'>Natural language lighting control</p>
        </div>
        """
    )

    with gr.Row(equal_height=True):
        with gr.Column(scale=7):
            command_box = gr.Textbox(
                label="Lighting command",
                placeholder="Try: irish flag, sunset, calm ocean, american police lights...",
                lines=2,
            )
        with gr.Column(scale=3, min_width=220):
            send_button = gr.Button("Send", variant="primary", size="lg")
            stop_button = gr.Button("Stop / Blackout", variant="secondary", size="lg")

    gr.Examples(examples=[[example] for example in EXAMPLE_COMMANDS], inputs=command_box)

    status_markdown = gr.Markdown("**Status:** Ready.\n")
    current_html = gr.HTML(empty_scene_html("No scene is currently running."))
    save_current_button = gr.Button("Save current scene", variant="secondary")

    gr.HTML("<div class='section-title'>Latest 10 scenes</div>")
    history_html_components = []
    history_play_buttons = []
    history_save_buttons = []
    for _ in range(MAX_HISTORY):
        with gr.Row(equal_height=True):
            history_html_components.append(gr.HTML(visible=False))
            with gr.Column(scale=1, min_width=150):
                history_play_buttons.append(gr.Button("Play", visible=False))
                history_save_buttons.append(gr.Button("Save", visible=False))

    gr.HTML("<div class='section-title'>Saved scenes</div>")
    saved_html_components = []
    saved_play_buttons = []
    saved_delete_buttons = []
    for _ in range(MAX_SAVED_ROWS):
        with gr.Row(equal_height=True):
            saved_html_components.append(gr.HTML(visible=False))
            with gr.Column(scale=1, min_width=150):
                saved_play_buttons.append(gr.Button("Play", visible=False))
                saved_delete_buttons.append(gr.Button("Delete", visible=False, variant="stop"))

    ui_outputs = [app_state, current_html, status_markdown]
    for i in range(MAX_HISTORY):
        ui_outputs.extend([
            history_html_components[i],
            history_play_buttons[i],
            history_save_buttons[i],
        ])
    for i in range(MAX_SAVED_ROWS):
        ui_outputs.extend([
            saved_html_components[i],
            saved_play_buttons[i],
            saved_delete_buttons[i],
        ])

    def submit_command(command, state):
        with _state_lock:
            state = run_prompt(command, state)
            return render_ui(state)

    def stop_handler(state):
        with _state_lock:
            state = stop_and_blackout(state)
            return render_ui(state)

    def save_current_handler(state):
        with _state_lock:
            state = save_current_scene(state)
            return render_ui(state)

    send_button.click(submit_command, inputs=[command_box, app_state], outputs=ui_outputs)
    command_box.submit(submit_command, inputs=[command_box, app_state], outputs=ui_outputs)
    stop_button.click(stop_handler, inputs=[app_state], outputs=ui_outputs)
    save_current_button.click(save_current_handler, inputs=[app_state], outputs=ui_outputs)

    for i in range(MAX_HISTORY):
        def make_history_play(index):
            def _handler(state):
                with _state_lock:
                    updated_state = replay_history(index, state)
                    return render_ui(updated_state)
            return _handler

        def make_history_save(index):
            def _handler(state):
                with _state_lock:
                    updated_state = save_history_scene(index, state)
                    return render_ui(updated_state)
            return _handler

        history_play_buttons[i].click(make_history_play(i), inputs=[app_state], outputs=ui_outputs)
        history_save_buttons[i].click(make_history_save(i), inputs=[app_state], outputs=ui_outputs)

    for i in range(MAX_SAVED_ROWS):
        def make_saved_play(index):
            def _handler(state):
                with _state_lock:
                    updated_state = replay_saved(index, state)
                    return render_ui(updated_state)
            return _handler

        def make_saved_delete(index):
            def _handler(state):
                with _state_lock:
                    updated_state = delete_saved_scene(index, state)
                    return render_ui(updated_state)
            return _handler

        saved_play_buttons[i].click(make_saved_play(i), inputs=[app_state], outputs=ui_outputs)
        saved_delete_buttons[i].click(make_saved_delete(i), inputs=[app_state], outputs=ui_outputs)

    demo.load(lambda state: render_ui(state), inputs=[app_state], outputs=ui_outputs)


if __name__ == "__main__":
    demo.launch(
        inbrowser=True,
        theme=gr.themes.Soft(),
        css=CSS,
    )
