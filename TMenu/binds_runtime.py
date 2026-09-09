from binds_config import BindsConfig
from binds_keyboard import KeyboardBindRouter


class BindsRuntime:
    def __init__(self, state):
        self.config = BindsConfig.load()
        self.keyboard_router = KeyboardBindRouter()
