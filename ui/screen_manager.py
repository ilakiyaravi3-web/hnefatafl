# ui/screen_manager.py

from ui.menu import MainMenu, SetupScreen_HumanVSAI, SetupScreen_AIVSAI, GameOverScreen

class ScreenManager:
    def __init__(self):
        self.screens = {}
        self.current = None
        self.game_callback = None  # set by main.py

    def setup(self):
        self.screens["menu"] = MainMenu(self)
        self.screens["setup"] = SetupScreen_HumanVSAI(self)
        self.screens["setup_ai"] = SetupScreen_AIVSAI(self)
        self.screens["game_over"] = GameOverScreen(self)

        self.current = self.screens["menu"]

    def go_to(self, name):
        self.current = self.screens[name]

    def start_game(self, config):
        if self.game_callback:
            self.game_callback(config)

    def draw(self, screen):
        self.current.draw(screen)

    def handle_event(self, event):
        self.current.handle_event(event)