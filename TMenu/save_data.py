"""
save_data.py
=============
Address data for the top-level SAVE tab's DIFFICULTY and STATS subtabs.

Difficulty is a single byte code (00-03) written to both addresses at once
so the saveable and active difficulty always agree:

    00 Easy, 01 Normal, 02 Hardcore, 03 Motorized
"""

SAVEABLE_DIFFICULTY_ADDRESS = 0x300746DF
ACTIVE_DIFFICULTY_ADDRESS = 0x30085447

DIFFICULTY_OPTIONS = [
    (0, "Easy"),
    (1, "Normal"),
    (2, "Hardcore"),
    (3, "Motorized"),
]

# Stats - BoardSales is a plain 4-byte big-endian int, get and set.
BOARD_SALES_ADDRESS = 0x30108764
