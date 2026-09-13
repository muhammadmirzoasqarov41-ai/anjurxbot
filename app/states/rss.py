"""
FSM States for RSS & Channel Aggregator workflows.
"""
from aiogram.fsm.state import State, StatesGroup


class AddRssState(StatesGroup):
    """Step-by-step workflow for adding a Website/RSS source."""
    waiting_for_url = State()
    waiting_for_destination = State()
    waiting_for_confirm = State()


class AddTelegramSourceState(StatesGroup):
    """Step-by-step workflow for adding a Telegram Channel source."""
    waiting_for_source = State()
    waiting_for_destination = State()
    waiting_for_confirm = State()


class ConnectChannelState(StatesGroup):
    """Step-by-step workflow for connecting a destination channel."""
    waiting_for_channel = State()
