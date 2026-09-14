"""
Unit tests specifically validating RSS category keyboards, models, and callback structures.
Ensures no NameError, correct typing, and exact callback query signatures.
"""
import unittest
from app.services.rss_storage import CategoryItem, SourceItem, ChannelItem, rss_storage
from app.keyboards.rss import (
    get_channel_categories_keyboard,
    get_category_sources_keyboard,
    get_channel_sources_keyboard,
    get_channel_schedule_keyboard,
    get_channels_list_keyboard,
    get_main_menu_keyboard,
)


class TestRssCategoryKeyboards(unittest.TestCase):

    def setUp(self):
        self.categories = [
            CategoryItem(id="cat_ozbekiston", name="O‘zbekiston", slug="ozbekiston", icon="flag", sort_order=1),
            CategoryItem(id="cat_jahon", name="Jahon", slug="jahon", icon="globe", sort_order=2),
            CategoryItem(id="cat_texnologiya", name="Texnologiya va IT", slug="texnologiya", icon="cpu", sort_order=3),
        ]
        self.sources = [
            SourceItem(id="src_kunuz", name="Kun.uz", url="https://kun.uz/feed", category_id="cat_ozbekiston"),
            SourceItem(id="src_daryouz", name="Daryo.uz", url="https://daryo.uz/feed", category_id="cat_ozbekiston"),
            SourceItem(id="src_bbcuz", name="BBC Uzbek", url="https://bbc.com/feed", category_id="cat_jahon"),
        ]
        self.sources_by_cat = {
            "cat_ozbekiston": [self.sources[0], self.sources[1]],
            "cat_jahon": [self.sources[2]],
            "cat_texnologiya": [],
        }
        self.channel = ChannelItem(
            chat_id=-1001234567890,
            title="Test Kanal",
            selected_sources=["src_kunuz"],
        )

    def test_channel_categories_keyboard(self):
        """Validates category list generation with proper counts and callback data."""
        kb = get_channel_categories_keyboard(
            channel_id=self.channel.chat_id,
            categories=self.categories,
            sources_by_cat=self.sources_by_cat,
            selected_source_ids=self.channel.selected_sources,
        )
        self.assertIsNotNone(kb)
        self.assertTrue(len(kb.inline_keyboard) > 0)

        # Collect callback data
        cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn(f"ch_cat_view:{self.channel.chat_id}:cat_ozbekiston", cbs)
        self.assertIn(f"ch_cat_view:{self.channel.chat_id}:cat_jahon", cbs)
        self.assertIn(f"ch_src_bulk:{self.channel.chat_id}:all:select", cbs)
        self.assertIn(f"ch_src_bulk:{self.channel.chat_id}:all:clear", cbs)
        self.assertIn(f"ch_view:{self.channel.chat_id}", cbs)

    def test_category_sources_keyboard(self):
        """Validates source checkboxes within a category and bulk select/clear."""
        cat = self.categories[0]
        cat_sources = self.sources_by_cat["cat_ozbekiston"]
        kb = get_category_sources_keyboard(
            channel_id=self.channel.chat_id,
            category=cat,
            sources=cat_sources,
            selected_source_ids=self.channel.selected_sources,
        )
        self.assertIsNotNone(kb)
        cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn(f"ch_src_toggle:{self.channel.chat_id}:cat_ozbekiston:src_kunuz", cbs)
        self.assertIn(f"ch_src_toggle:{self.channel.chat_id}:cat_ozbekiston:src_daryouz", cbs)
        self.assertIn(f"ch_src_bulk:{self.channel.chat_id}:cat_ozbekiston:select", cbs)
        self.assertIn(f"ch_src_bulk:{self.channel.chat_id}:cat_ozbekiston:clear", cbs)
        self.assertIn(f"ch_sources:{self.channel.chat_id}", cbs)

    def test_channel_schedule_keyboard(self):
        """Validates schedule configuration keyboard."""
        kb = get_channel_schedule_keyboard(self.channel)
        self.assertIsNotNone(kb)
        cbs = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn(f"ch_set_limit:{self.channel.chat_id}:1", cbs)
        self.assertIn(f"ch_set_limit:{self.channel.chat_id}:2", cbs)
        self.assertIn(f"ch_set_limit:{self.channel.chat_id}:3", cbs)
        self.assertIn(f"ch_set_sched:{self.channel.chat_id}:instant", cbs)
        self.assertIn(f"ch_set_sched:{self.channel.chat_id}:custom", cbs)

    def test_main_menu_keyboard(self):
        """Normal user vs super admin main menu buttons."""
        kb_normal = get_main_menu_keyboard(user_id=12345)
        cbs_normal = [btn.callback_data for row in kb_normal.inline_keyboard for btn in row if btn.callback_data]
        self.assertNotIn("admin_panel_main", cbs_normal)

        kb_admin = get_main_menu_keyboard(user_id=8157452043)
        cbs_admin = [btn.callback_data for row in kb_admin.inline_keyboard for btn in row if btn.callback_data]
        self.assertIn("admin_panel_main", cbs_admin)


if __name__ == "__main__":
    unittest.main()
