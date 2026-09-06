"""
FSM States for AnjurXBot Admin Operations.
"""
from aiogram.fsm.state import State, StatesGroup


class ChannelAddState(StatesGroup):
    waiting_for_channel = State()


class BadWordsState(StatesGroup):
    waiting_for_word = State()


class FloodThresholdState(StatesGroup):
    waiting_for_limit = State()


class WarningLimitState(StatesGroup):
    waiting_for_limit = State()


class BroadcastState(StatesGroup):
    waiting_for_message = State()
