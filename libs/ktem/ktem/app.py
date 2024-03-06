from pathlib import Path
from typing import Optional

import gradio as gr
import pluggy
from ktem import extension_protocol
from ktem.components import reasonings
from ktem.exceptions import HookAlreadyDeclared, HookNotDeclared
from ktem.index import IndexManager
from ktem.settings import BaseSettingGroup, SettingGroup, SettingReasoningGroup
from theflow.settings import settings
from theflow.utils.modules import import_dotted_string


class BaseApp:
    """The main app of Kotaemon

    The main application contains app-level information:
        - setting state
        - user id

    Also contains registering methods for:
        - reasoning pipelines
        - indexing & retrieval pipelines

    App life-cycle:
        - Render
        - Declare public events
        - Subscribe public events
        - Register events
    """

    def __init__(self):
        self.dev_mode = getattr(settings, "KH_MODE", "") == "dev"
        self._theme = gr.themes.Base(
            font=("ui-sans-serif", "system-ui", "sans-serif"),
            font_mono=("ui-monospace", "Consolas", "monospace"),
        )

        dir_assets = Path(__file__).parent / "assets"
        with (dir_assets / "css" / "main.css").open() as fi:
            self._css = fi.read()
        with (dir_assets / "js" / "main.js").open() as fi:
            self._js = fi.read()
        self._favicon = str(dir_assets / "img" / "favicon.svg")

        self.default_settings = SettingGroup(
            application=BaseSettingGroup(settings=settings.SETTINGS_APP),
            reasoning=SettingReasoningGroup(settings=settings.SETTINGS_REASONING),
        )

        self._callbacks: dict[str, list] = {}
        self._events: dict[str, list] = {}

        self.register_extensions()
        self.register_reasonings()
        self.initialize_indices()

        self.default_settings.reasoning.finalize()
        self.default_settings.index.finalize()
        self.settings_state = gr.State(self.default_settings.flatten())

        self.user_id = gr.State(1 if self.dev_mode else None)

    def initialize_indices(self):
        """Create the index manager, start indices, and register to app settings"""
        self.index_manager = IndexManager(self)
        self.index_manager.on_application_startup()

        for index in self.index_manager.indices:
            options = index.get_user_settings()
            self.default_settings.index.options[index.id] = BaseSettingGroup(
                settings=options
            )

    def register_reasonings(self):
        """Register the reasoning components from app settings"""
        if getattr(settings, "KH_REASONINGS", None) is None:
            return

        for value in settings.KH_REASONINGS:
            reasoning_cls = import_dotted_string(value, safe=False)
            rid = reasoning_cls.get_info()["id"]
            reasonings[rid] = reasoning_cls
            options = reasoning_cls().get_user_settings()
            self.default_settings.reasoning.options[rid] = BaseSettingGroup(
                settings=options
            )

    def register_extensions(self):
        """Register installed extensions"""
        self.exman = pluggy.PluginManager("ktem")
        self.exman.add_hookspecs(extension_protocol)
        self.exman.load_setuptools_entrypoints("ktem")

        # retrieve and register extension declarations
        extension_declarations = self.exman.hook.ktem_declare_extensions()
        for extension_declaration in extension_declarations:
            # if already in database, with the same version: skip

            # otherwise,
            # remove the old information from the database if it exists
            # store the information into the database

            functionality = extension_declaration["functionality"]

            # update the reasoning information
            if "reasoning" in functionality:
                for rid, rdec in functionality["reasoning"].items():
                    unique_rid = f"{extension_declaration['id']}/{rid}"
                    self.default_settings.reasoning.options[
                        unique_rid
                    ] = BaseSettingGroup(
                        settings=rdec["settings"],
                    )

    def declare_event(self, name: str):
        """Declare a public gradio event for other components to subscribe to

        Args:
            name: The name of the event
        """
        if name in self._events:
            raise HookAlreadyDeclared(f"Hook {name} is already declared")
        self._events[name] = []

    def subscribe_event(self, name: str, definition: dict):
        """Register a hook for the app

        Args:
            name: The name of the hook
            hook: The hook to be registered
        """
        if name not in self._events:
            raise HookNotDeclared(f"Hook {name} is not declared")
        self._events[name].append(definition)

    def get_event(self, name) -> list[dict]:
        if name not in self._events:
            raise HookNotDeclared(f"Hook {name} is not declared")

        return self._events[name]

    def ui(self):
        raise NotImplementedError

    def make(self):
        with gr.Blocks(
            theme=self._theme,
            css=self._css,
            title="Kotaemon",
            analytics_enabled=False,
        ) as demo:
            self.app = demo
            self.settings_state.render()
            self.user_id.render()

            self.ui()

            for value in self.__dict__.values():
                if isinstance(value, BasePage):
                    value.declare_public_events()

            for value in self.__dict__.values():
                if isinstance(value, BasePage):
                    value.subscribe_public_events()

            for value in self.__dict__.values():
                if isinstance(value, BasePage):
                    value.register_events()

            for value in self.__dict__.values():
                if isinstance(value, BasePage):
                    value.on_app_created()

            demo.load(lambda: None, None, None, js=f"() => {{{self._js}}}")

        return demo


class BasePage:
    """The logic of the Kotaemon app"""

    public_events: list[str] = []

    def __init__(self, app):
        self._app = app

    def on_building_ui(self):
        """Build the UI of the app"""

    def on_subscribe_public_events(self):
        """Subscribe to the declared public event of the app"""

    def on_register_events(self):
        """Register all events to the app"""

    def _on_app_created(self):
        """Called when the app is created"""

    def as_gradio_component(self) -> Optional[gr.components.Component]:
        """Return the gradio components responsible for events

        Note: in ideal scenario, this method shouldn't be necessary.
        """
        return None

    def render(self):
        for value in self.__dict__.values():
            if isinstance(value, gr.blocks.Block):
                value.render()
            if isinstance(value, BasePage):
                value.render()

    def unrender(self):
        for value in self.__dict__.values():
            if isinstance(value, gr.blocks.Block):
                value.unrender()
            if isinstance(value, BasePage):
                value.unrender()

    def declare_public_events(self):
        """Declare an event for the app"""
        for event in self.public_events:
            self._app.declare_event(event)

        for value in self.__dict__.values():
            if isinstance(value, BasePage):
                value.declare_public_events()

    def subscribe_public_events(self):
        """Subscribe to an event"""
        self.on_subscribe_public_events()
        for value in self.__dict__.values():
            if isinstance(value, BasePage):
                value.subscribe_public_events()

    def register_events(self):
        """Register all events"""
        self.on_register_events()
        for value in self.__dict__.values():
            if isinstance(value, BasePage):
                value.register_events()

    def on_app_created(self):
        """Execute on app created callbacks"""
        self._on_app_created()
        for value in self.__dict__.values():
            if isinstance(value, BasePage):
                value.on_app_created()
