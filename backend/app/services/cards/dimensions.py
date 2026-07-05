"""
CR80 ID card dimensions and layout constants.

CR80 standard:  85.6 mm × 54.0 mm
In points:      242.6 pt × 153.1 pt  (1 pt = 1/72 inch, 1 inch = 25.4 mm)
"""

MM = 2.8346         # points per mm

# Card physical dimensions
CARD_W = 85.6 * MM   # 242.6 pt
CARD_H = 54.0 * MM   # 153.1 pt

# Safe margin inside card (3 mm bleed)
MARGIN = 3.0 * MM

# Photo area — left side
PHOTO_X = MARGIN
PHOTO_Y = MARGIN + 8 * MM
PHOTO_W = 22.0 * MM
PHOTO_H = 28.0 * MM

# Header strip height (company name)
HEADER_H = 9.0 * MM

# Text area — right of photo
TEXT_X = PHOTO_X + PHOTO_W + 3.0 * MM
TEXT_W = CARD_W - TEXT_X - MARGIN

# Footer strip height (valid date + access)
FOOTER_H = 8.0 * MM
FOOTER_Y = MARGIN

# Colour defaults — HR can override via company settings
EMPLOYEE_BG     = (0.118, 0.251, 0.686)    # #1E40AF  deep blue
EMPLOYEE_HEADER = (0.071, 0.157, 0.518)    # darker blue for header/footer
EMPLOYEE_TEXT   = (1.0, 1.0, 1.0)          # white text on colour

CONTRACTOR_BG     = (0.914, 0.357, 0.047)  # #EA5B0C  orange
CONTRACTOR_HEADER = (0.639, 0.231, 0.008)  # darker orange
CONTRACTOR_TEXT   = (1.0, 1.0, 1.0)

DARK_TEXT   = (0.1, 0.1, 0.1)             # near-black for light backgrounds
WHITE       = (1.0, 1.0, 1.0)
ACCENT_GOLD = (0.957, 0.784, 0.200)        # subtle gold stripe


def hex_to_rgb(hex_colour: str) -> tuple[float, float, float]:
    """Convert '#1E40AF' to (0.118, 0.251, 0.686) for ReportLab."""
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
