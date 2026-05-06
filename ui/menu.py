#PERSON A: Anjali
# Main Menu
# Game Setup
# Game Over Screen

# ui/menu.py
import pygame

WIDTH, HEIGHT = 800, 660

# ─────────────────────────────────────────────────────────────
# Reusable Button
# ─────────────────────────────────────────────────────────────
class Button:
    def __init__(self, text, rect, action):
        self.text = text
        self.rect = pygame.Rect(rect)
        self.action = action
        # self.base_color = (85, 61, 54)
        # self.hover_color = (40, 26, 13)
        
        self.base_color  = (49, 13, 0)     # dark brown
        self.hover_color = (85, 52, 32)   # gold
        # text_color  = (255, 255, 255)  # white

    def draw(self, screen, font):
        
        mouse_pos = pygame.mouse.get_pos()
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.base_color
        pygame.draw.rect(screen, color, self.rect)

        text_surf = font.render(self.text, True, (255,255,255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.action()


# ─────────────────────────────────────────────────────────────
# Main Menu
# ─────────────────────────────────────────────────────────────
class MainMenu:
    def __init__(self, manager):
        self.manager = manager
        self.font = pygame.font.SysFont("segoeui", 40, bold=True)

        self.buttons = [
            Button("Human vs AI", (300, 200, 260, 50), lambda: manager.go_to("setup")),
            Button("AI vs AI", (300, 270, 260, 50), lambda: manager.go_to("setup_ai")),
            Button("Watch Replay", (300, 340, 260, 50), lambda: print("Replay TBD"))
        ]

    def draw(self, screen):
        screen.fill((59, 30, 16))
        button_width = 280
        button_height = 80
        start_y = 320  
        gap = 15
        
        title_font = pygame.font.SysFont("segoeui", 28)
        main_font  = pygame.font.SysFont("segoeui", 50, bold=True)
        sub_font   = pygame.font.SysFont("segoeui", 22)

        title = title_font.render("Welcome to", True, (255,255,255))
        title2 = main_font.render("Hnefatafl", True, (255,219,0))
        title3 = sub_font.render("The Viking Chess", True, (255,255,255))

        # Center each line
        title_rect = title.get_rect(center=(400, 120))
        title2_rect = title2.get_rect(center=(400, 180))
        title3_rect = title3.get_rect(center=(400, 240))

        screen.blit(title, title_rect)
        screen.blit(title2, title2_rect)
        screen.blit(title3, title3_rect)
        
        selector_text =sub_font.render("Please select the mode:", True, (255,255,255))
        selector_rect = selector_text.get_rect(center=(400, 280))
        screen.blit(selector_text, selector_rect)
        for i, b in enumerate(self.buttons):
            # Center horizontally
            x = (800 - button_width) // 2
            y = start_y + i * (button_height + gap)

            # Update button rect
            b.rect = pygame.Rect(x, y, button_width, button_height)

            b.draw(screen, self.font)

    def handle_event(self, event):
        for b in self.buttons:
            b.handle_event(event)


# ─────────────────────────────────────────────────────────────
# Setup Screen
# ─────────────────────────────────────────────────────────────



class Dropdown:
    def __init__(self, x, y, w, h, options, default):
        self.rect = pygame.Rect(x, y, w, h)
        self.options = options
        self.selected = default
        self.open = False

        self.base_color = (255, 255, 255)
        self.hover_color = (120, 120, 120)

        # Arrow color (NEW)
        self.arrow_color = (70, 70, 70)

        self.font = pygame.font.SysFont("segoeui", 22)

    def draw(self, screen):
        # Main box
        pygame.draw.rect(screen, self.base_color, self.rect, border_radius=6)

        # Selected text
        text = self.font.render(self.selected, True, (70, 70, 70))
        screen.blit(text, text.get_rect(center=self.rect.center))

        # ===== ARROW (NEW FIXED PART) =====
        cx = self.rect.right - 25
        cy = self.rect.centery

        if self.open:
            # UP arrow ▲
            points = [
                (cx - 6, cy + 4),
                (cx + 6, cy + 4),
                (cx, cy - 4)
            ]
        else:
            # DOWN arrow ▼
            points = [
                (cx - 6, cy - 4),
                (cx + 6, cy - 4),
                (cx, cy + 4)
            ]

        pygame.draw.polygon(screen, self.arrow_color, points)
        # ==================================

        # Dropdown list
        if self.open:
            for i, option in enumerate(self.options):
                option_rect = pygame.Rect(
                    self.rect.x,
                    self.rect.y + (i + 1) * self.rect.height,
                    self.rect.width,
                    self.rect.height
                )

                mouse_pos = pygame.mouse.get_pos()

                color = self.hover_color if option_rect.collidepoint(mouse_pos) else self.base_color
                pygame.draw.rect(screen, color, option_rect, border_radius=6)

                txt = self.font.render(option, True, (0, 0, 0))
                screen.blit(txt, txt.get_rect(center=option_rect.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Click main box
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
            else:
                # Check options
                if self.open:
                    for i, option in enumerate(self.options):
                        option_rect = pygame.Rect(
                            self.rect.x,
                            self.rect.y + (i + 1) * self.rect.height,
                            self.rect.width,
                            self.rect.height
                        )

                        if option_rect.collidepoint(event.pos):
                            self.selected = option
                            self.open = False                         
class SetupScreen_HumanVSAI:
    def __init__(self, manager):
        self.manager = manager
        self.font = pygame.font.SysFont("segoeui", 28, bold=True)
        # Initialize default values FIRST
        self.side = "Attacker"
        self.agent = "Random"
        
        self.side_dropdown = Dropdown(
            350, 150, 250, 40,
            ["Attacker", "Defender"],
            self.side
        )

        self.agent_dropdown = Dropdown(
            350, 300, 250, 40,
            ["Random", "Heuristic", "MCTS"],
            self.agent
        )

        self.buttons = [
            Button("Start Game", (300, 500, 200, 50), self.start_game),
            Button("Back", (300, 580, 200, 50), lambda: manager.go_to("menu"))
        ]

    def start_game(self):
        self.manager.start_game({
            "side": self.side,
            "agent": self.agent
        })

    def draw(self, screen):
        screen.fill((59, 30, 16))
        
        
        
        
        
        # Labels
        side_label = self.font.render("Select Side:", True, (255,255,255))
        agent_label = self.font.render("Select Opponent Agent:", True, (255,255,255))

        screen.blit(side_label, (150, 150))
        screen.blit(agent_label, (25, 300))

        # Draw dropdowns
        self.side_dropdown.draw(screen)
        self.agent_dropdown.draw(screen)
        
        r = self.side_dropdown.rect

        pygame.draw.polygon(screen, (255,255,255), [
            (r.right - 20, r.centery - 5),
            (r.right - 10, r.centery - 5),
            (r.right - 15, r.centery + 5)
        ])
        
        r = self.agent_dropdown.rect

        pygame.draw.polygon(screen, (255,255,255), [
            (r.right - 20, r.centery - 5),
            (r.right - 10, r.centery - 5),
            (r.right - 15, r.centery + 5)
        ])
        # Buttons
        for b in self.buttons:
            b.draw(screen, self.font)

    def handle_event(self, event):
        self.side_dropdown.handle_event(event)
        self.agent_dropdown.handle_event(event)

        # Update values
        self.side = self.side_dropdown.selected
        self.agent = self.agent_dropdown.selected

        for b in self.buttons:
            b.handle_event(event)

class SetupScreen_AIVSAI:
    def __init__(self, manager):
        self.manager = manager
        self.font = pygame.font.SysFont("segoeui", 28, bold=True)
        # Initialize default values FIRST
        self.defender = "Random"
        self.attacker = "Random"
        
        self.defender_dropdown = Dropdown(
            400, 150, 250, 40,
            ["Random", "Heuristic", "MCTS"],
            self.defender
        )

        self.attacker_dropdown = Dropdown(
            400, 350, 250, 40,
            ["Random", "Heuristic", "MCTS"],
            self.attacker
        )

        self.buttons = [
            Button("Start Game", (150, 520, 200, 50), self.start_game),
            Button("Back", (400, 520, 200, 50), lambda: manager.go_to("menu"))
        ]

    def start_game(self):
        self.manager.start_game({
            "defender": self.defender,
            "attacker": self.attacker
        })

    def draw(self, screen):
        screen.fill((59, 30, 16))
        
        
        
        
        
        # Labels
        defender_label = self.font.render("Select Defender Agent:", True, (255,255,255))
        attacker_label = self.font.render("Select Attacker Agent:", True, (255,255,255))

        screen.blit(defender_label, (45, 150))
        screen.blit(attacker_label, (50, 350))

        # Draw dropdowns
        self.defender_dropdown.draw(screen)
        self.attacker_dropdown.draw(screen)
        
        r = self.defender_dropdown.rect

        pygame.draw.polygon(screen, (255,255,255), [
            (r.right - 20, r.centery - 5),
            (r.right - 10, r.centery - 5),
            (r.right - 15, r.centery + 5)
        ])
        
        r = self.attacker_dropdown.rect

        pygame.draw.polygon(screen, (255,255,255), [
            (r.right - 20, r.centery - 5),
            (r.right - 10, r.centery - 5),
            (r.right - 15, r.centery + 5)
        ])
        # Buttons
        for b in self.buttons:
            b.draw(screen, self.font)

    def handle_event(self, event):
        self.defender_dropdown.handle_event(event)
        self.attacker_dropdown.handle_event(event)

        # Update values
        self.defender = self.defender_dropdown.selected
        self.attacker = self.attacker_dropdown.selected

        for b in self.buttons:
            b.handle_event(event)


# ─────────────────────────────────────────────────────────────
# Game Over Screen
# ─────────────────────────────────────────────────────────────
class GameOverScreen:
    def __init__(self, manager):
        self.manager = manager
        self.font = pygame.font.SysFont("segoeui", 32, bold= True)

        self.winner = ""
        self.summary = ""

        self.buttons = [
            Button("Play Again", (300, 400, 200, 50), lambda: manager.go_to("setup")),
            Button("Main Menu", (300, 470, 200, 50), lambda: manager.go_to("menu"))
        ]

    def set_data(self, winner, summary):
        self.winner = winner
        self.summary = summary

    def draw(self, screen):
        screen.fill((59, 30, 16))

        win_text = self.font.render(self.winner, True, (255,255,0))
        sum_text = self.font.render(self.summary, True, (200,200,200))

        screen.blit(win_text, (250, 200))
        screen.blit(sum_text, (200, 250))

        for b in self.buttons:
            b.draw(screen, self.font)

    def handle_event(self, event):
        for b in self.buttons:
            b.handle_event(event)