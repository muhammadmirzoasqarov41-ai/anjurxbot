from aiogram.types import Message

from app.keyboards.admin import groups_list_keyboard
from app.services.dedup_service import UpdateDedupService
from app.services.flood_service import check_flood, cleanup_flood_cache, reset_flood
from app.services.rate_limit_service import RateLimitService
from app.services.spam_service import (
    contains_bad_word,
    has_link,
    is_advertisement,
    is_repeated_message,
)


def test_rate_limit_allows_limit_then_blocks():
    limiter = RateLimitService()
    assert limiter.allow("test", 10, 2, 60)
    assert limiter.allow("test", 10, 2, 60)
    assert not limiter.allow("test", 10, 2, 60)
    assert limiter.allow("test", 11, 2, 60)


def test_duplicate_updates_are_bounded_and_rejected():
    dedup = UpdateDedupService(max_size=2, ttl=60)
    assert dedup.first_seen(1)
    assert not dedup.first_seen(1)
    assert dedup.first_seen(2)
    assert dedup.first_seen(3)


def test_flood_detects_and_resets():
    chat_id, user_id = 991001, 991002
    reset_flood(chat_id, user_id)
    assert not check_flood(chat_id, user_id, 2, 5)
    assert not check_flood(chat_id, user_id, 2, 5)
    assert check_flood(chat_id, user_id, 2, 5)
    reset_flood(chat_id, user_id)
    cleanup_flood_cache()


def test_repeat_normalizes_case_and_whitespace():
    chat_id, user_id = 992001, 992002
    messages = [Message(message_id=index, date=0, chat={"id": chat_id, "type": "group"}, text=text)
                for index, text in enumerate(["  Hello   world ", "hello world", "HELLO WORLD"], 1)]
    assert not is_repeated_message(chat_id, user_id, messages[0])
    assert not is_repeated_message(chat_id, user_id, messages[1])
    assert is_repeated_message(chat_id, user_id, messages[2])


def test_content_detectors():
    link_message = Message(message_id=1, date=0, chat={"id": 1, "type": "group"}, text="Visit https://example.com")
    ad_message = Message(message_id=2, date=0, chat={"id": 1, "type": "group"}, text="Sotiladi, arzon! +998 90 123 45 67")
    plain_message = Message(message_id=3, date=0, chat={"id": 1, "type": "group"}, text="Assalomu alaykum")
    assert has_link(link_message)
    assert is_advertisement(ad_message)
    assert not is_advertisement(plain_message)
    assert contains_bad_word(plain_message.model_copy(update={"text": "Bu yomon so'z"}), ["yomon"])


def test_group_keyboard_contains_group_callback():
    markup = groups_list_keyboard([{"chat_id": -1001, "title": "Test"}], "guard")
    assert markup.inline_keyboard[0][0].callback_data == "ap:g:-1001:guard"
