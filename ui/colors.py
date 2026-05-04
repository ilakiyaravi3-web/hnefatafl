# ui/colors.py
# Shared color palette for all UI modules — do not edit without telling the team

BACKGROUND    = (30, 30, 30)

# Board squares
CELL_LIGHT    = (240, 217, 181)
CELL_DARK     = (181, 136, 99)
THRONE        = (139, 0, 0)        # center square — only king can stop here
CORNER        = (212, 175, 55)     # escape squares for the king
GRID_LINE     = (80, 80, 80)

# Piece colors
ATTACKER      = (180, 40, 40)      # red
ATTACKER_OUT  = (220, 80, 80)      # red outline
DEFENDER      = (60, 100, 180)     # blue
DEFENDER_OUT  = (100, 140, 220)    # blue outline
KING          = (212, 175, 55)     # gold
KING_OUT      = (255, 215, 0)      # bright gold outline

# Selection and highlights
SELECTED_RING = (255, 255, 0)      # yellow ring around selected piece
LEGAL_MOVE    = (100, 200, 100)    # green overlay for valid destinations
LAST_MOVE     = (200, 200, 50)     # yellow tint on last moved square

# Text
TEXT_PRIMARY  = (255, 255, 255)
TEXT_SECONDARY = (180, 180, 180)
