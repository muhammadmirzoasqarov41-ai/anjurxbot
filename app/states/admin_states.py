"""
Admin panel FSM states.

Used by the interactive admin panel flows:
  - FloodSettingsStates: change flood_limit / flood_window / mute_duration
  - BadWordStates:       add / remove bad words
  - FsubChannelStates:   add / remove force-subscribe channels

Each FSM handler stores 'group_id' in state data so it knows
which group to update after the user provides input.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class FloodSettingsStates(StatesGroup):
    """Interactive flood parameter editing."""
    waiting_limit = State()   # new flood_limit (int)
    waiting_window = State()  # new flood_window (int, seconds)
    waiting_mute = State()    # new mute_duration (int, seconds)


class BadWordStates(StatesGroup):
    """Interactive bad-word management."""
    waiting_add = State()  # word to add
    waiting_del = State()  # word to remove


class FsubChannelStates(StatesGroup):
    """Interactive force-subscribe channel management."""
    waiting_add = State()  # channel username or ID to add
