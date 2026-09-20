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


class AdminAddSourceState(StatesGroup):
    """Super Admin state for adding a verified RSS/Atom source."""
    waiting_for_url = State()
    waiting_for_name = State()


class SetScheduleTimesState(StatesGroup):
    """Workflow for user entering custom schedule times (e.g. 09:30, 14:00, 20:00)."""
    waiting_for_times = State()


class ChannelFooterState(StatesGroup):
    """Workflow for user configuring custom channel footer text or link/button."""
    waiting_for_text = State()
    waiting_for_url = State()

