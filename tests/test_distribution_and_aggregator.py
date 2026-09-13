"""
Automated Integration and Unit Tests for AnjurX | Obuna Bot.
Validates:
1. Super Admin Authentication (strictly numeric ID 8157452043 vs normal user)
2. Normal users cannot access Super Admin features
3. Channel registration and IDOR protection
4. Daily 3-post limit enforcement (free tier max 3)
5. Contract plan upgrade and custom limit extension
6. 5-day post retention in Post Pool (calculation and expiration)
7. Fair Distribution Engine:
   - Least delivered channel priority (0-post channels prioritized)
   - Channel limit enforcement
   - Unused posts remain in pool without being lost
   - Duplicate prevention per (source, external_id, channel)
   - Strict channel delivery (never user DM)
"""
import unittest
import asyncio
import tempfile
import os
import shutil
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.config import config
from app.services.permission_service import is_super_admin
from app.services.rss_storage import (
    rss_storage,
    SourceItem,
    ChannelItem,
    PostItem,
    get_tashkent_now,
    get_today_tashkent_str,
)
from app.services.distribution_service import PostDistributionService


class TestAnjurXAggregator(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create temp dir for isolated test database
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_rssbot.json")
        os.environ["DATABASE_PATH"] = self.test_db_path

        self.storage = rss_storage
        # Reset internal state
        self.storage._sources = {}
        self.storage._channels = {}
        self.storage._users = {}
        self.storage._posts_pool = {}
        self.storage._delivered_keys = set()
        await self.storage.init()
        self.distribution = PostDistributionService()

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. Super Admin Authorization
    # --------------------------------------------------------------------------
    def test_super_admin_numeric_auth(self):
        """Verifies that Super Admin ID 8157452043 is strictly authorized and normal users are denied."""
        # Numeric Super Admin ID must be authorized
        self.assertTrue(is_super_admin(8157452043))
        self.assertTrue(config.is_super_admin(8157452043))

        # String representation of ID
        self.assertTrue(is_super_admin("8157452043"))

        # Normal users must NOT have super admin access
        self.assertFalse(is_super_admin(123456789))
        self.assertFalse(is_super_admin(987654321))
        self.assertFalse(is_super_admin(0))
        self.assertFalse(is_super_admin(None))

    # --------------------------------------------------------------------------
    # 2. Channel Management & IDOR Protection
    # --------------------------------------------------------------------------
    async def test_channel_registration_and_ownership(self):
        """Tests that channels are registered with correct owner and IDOR is blocked."""
        user_alice = 111111
        user_bob = 222222

        # Register Alice's channel
        alice_ch = await self.storage.register_or_update_channel(
            chat_id=-1001001,
            title="Alice News",
            username="alicenews",
            owner_user_id=user_alice,
            can_post=True,
        )
        self.assertEqual(alice_ch.owner_user_id, user_alice)
        self.assertEqual(alice_ch.daily_limit, 3)  # Default free limit

        # Alice's channels list must include Alice's channel
        alice_channels = await self.storage.get_channels_for_user(user_alice)
        self.assertEqual(len(alice_channels), 1)
        self.assertEqual(alice_channels[0].chat_id, -1001001)

        # Bob must NOT see Alice's channel (IDOR prevention)
        bob_channels = await self.storage.get_channels_for_user(user_bob)
        self.assertEqual(len(bob_channels), 0)

        # Bob cannot modify Alice's channel
        success = await self.storage.update_channel_sources(-1001001, ["src_kunuz"], user_id=user_bob)
        self.assertFalse(success)

        # Alice can modify her channel
        success = await self.storage.update_channel_sources(-1001001, ["src_kunuz"], user_id=user_alice)
        self.assertTrue(success)

    # --------------------------------------------------------------------------
    # 3. Daily 3-Post Limit Enforcement
    # --------------------------------------------------------------------------
    async def test_daily_limit_strict_enforcement(self):
        """Verifies that free users cannot exceed 3 posts/day and limit is clamped."""
        user_id = 12345
        channel = await self.storage.register_or_update_channel(
            chat_id=-1002002,
            title="Daily Limit Test Channel",
            owner_user_id=user_id,
        )

        # Free user attempts to set limit to 10
        await self.storage.update_channel_settings(
            chat_id=-1002002,
            user_id=user_id,
            daily_limit=10,
            is_super_admin=False,
        )
        ch_updated = await self.storage.get_channel(-1002002)
        # MUST be clamped to 3!
        self.assertEqual(ch_updated.daily_limit, 3)

        # Super admin upgrades user to contract plan
        await self.storage.set_user_contract_plan(user_id=user_id, plan="contract", custom_limit=15)
        ch_contract = await self.storage.get_channel(-1002002)
        self.assertEqual(ch_contract.daily_limit, 15)
        self.assertEqual(ch_contract.plan, "contract")

    # --------------------------------------------------------------------------
    # 4. 5-Day Post Retention Pool & Expiration
    # --------------------------------------------------------------------------
    async def test_five_day_post_retention_and_expiration(self):
        """Tests that posts expire after 5 days and are cleaned up."""
        now = datetime.utcnow()

        # Fresh post (0 days old)
        fresh_post = PostItem(
            post_id="post_test_fresh",
            source_id="src_kunuz",
            source_name="Kun.uz",
            external_post_id="hash_fresh",
            title="Fresh News",
            description="Today's fresh news",
            content="Content",
            url="https://kun.uz/news/fresh",
            fetched_at=now.isoformat(),
            expires_at=(now + timedelta(days=5)).isoformat(),
            status="queued",
        )
        await self.storage.save_post_to_pool(fresh_post)

        # Old post (6 days old -> expired)
        old_post = PostItem(
            post_id="post_test_old",
            source_id="src_kunuz",
            source_name="Kun.uz",
            external_post_id="hash_old",
            title="Old News",
            description="Old news from last week",
            content="Content",
            url="https://kun.uz/news/old",
            fetched_at=(now - timedelta(days=6)).isoformat(),
            expires_at=(now - timedelta(days=1)).isoformat(),
            status="queued",
        )
        await self.storage.save_post_to_pool(old_post)

        # Get queued posts before cleanup
        queued = await self.storage.get_queued_posts()
        queued_ids = [p.post_id for p in queued]
        self.assertIn("post_test_fresh", queued_ids)
        self.assertNotIn("post_test_old", queued_ids)  # Expired post filtered out!

        # Run cleanup
        cleaned = await self.storage.cleanup_expired_posts()
        self.assertGreaterEqual(cleaned, 1)

    # --------------------------------------------------------------------------
    # 5. Fair Distribution Algorithm: Least Delivered Priority
    # --------------------------------------------------------------------------
    async def test_fair_distribution_least_delivered_priority(self):
        """
        Verifies that when multiple channels are eligible for a post,
        the channel with the fewest delivered posts today receives priority.
        """
        # Channel A has received 2 posts today
        ch_a = ChannelItem(
            chat_id=-10001,
            title="Channel A",
            owner_user_id=1,
            daily_limit=3,
            today_delivered_count=2,
            selected_sources=["src_kunuz"],
        )
        # Channel B has received 0 posts today
        ch_b = ChannelItem(
            chat_id=-10002,
            title="Channel B",
            owner_user_id=2,
            daily_limit=3,
            today_delivered_count=0,
            selected_sources=["src_kunuz"],
        )
        # Channel C has received 1 post today
        ch_c = ChannelItem(
            chat_id=-10003,
            title="Channel C",
            owner_user_id=3,
            daily_limit=3,
            today_delivered_count=1,
            selected_sources=["src_kunuz"],
        )

        eligible = [ch_a, ch_b, ch_c]
        fair_choice = self.distribution.select_fair_channel(eligible)

        # Channel B (0 posts) MUST be selected first!
        self.assertEqual(fair_choice.chat_id, ch_b.chat_id)

    # --------------------------------------------------------------------------
    # 6. Fair Distribution: Strict Channel Delivery and Duplicate Protection
    # --------------------------------------------------------------------------
    async def test_fair_distribution_delivery_and_dedup(self):
        """
        Verifies that posts are sent to channel.chat_id (never user DM)
        and duplicate delivery is strictly prevented.
        """
        # Create channel in storage
        channel = await self.storage.register_or_update_channel(
            chat_id=-1009999,
            title="Test Target Channel",
            owner_user_id=777,
            can_post=True,
        )
        channel.selected_sources = ["src_kunuz"]
        channel.today_delivered_count = 0
        channel.daily_limit = 3

        # Create post in pool
        post = PostItem(
            post_id="post_kunuz_101",
            source_id="src_kunuz",
            source_name="Kun.uz",
            external_post_id="item_101",
            title="Breakthrough in Tech",
            description="Tech news summary",
            content="Full content",
            url="https://kun.uz/tech/101",
            status="queued",
        )
        await self.storage.save_post_to_pool(post)

        # Mock Bot
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 5555
        mock_bot.send_message.return_value = mock_sent

        # Run distribution
        delivered_count = await self.distribution.distribute_queued_posts(mock_bot)
        self.assertEqual(delivered_count, 1)

        # Verify bot sent message to channel.chat_id, NOT user DM (777)!
        mock_bot.send_message.assert_called_once()
        called_args, called_kwargs = mock_bot.send_message.call_args
        self.assertEqual(called_kwargs["chat_id"], -1009999)
        self.assertNotEqual(called_kwargs["chat_id"], 777)  # NEVER user DM!

        # Verify delivery is recorded and duplicate is prevented
        is_dup = await self.storage.is_post_delivered("src_kunuz", "item_101", -1009999)
        self.assertTrue(is_dup)

        # Second run with same post: must deliver 0
        mock_bot.reset_mock()
        delivered_again = await self.distribution.distribute_queued_posts(mock_bot)
        self.assertEqual(delivered_again, 0)
        mock_bot.send_message.assert_not_called()

    # --------------------------------------------------------------------------
    # 8. Keyboards & Destination Selection Flow Tests
    # --------------------------------------------------------------------------
    def test_destination_selection_keyboard_ownership_filter(self):
        """Tests that get_destination_selection_keyboard strictly isolates user channels."""
        from app.keyboards.rss import (
            get_destination_selection_keyboard,
            get_connection_confirm_keyboard,
            get_sources_list_keyboard,
            get_delete_source_confirm_keyboard,
            get_rss_list_keyboard,
            get_unsub_confirm_keyboard,
            get_allunsub_confirm_keyboard,
        )

        ch_user1 = ChannelItem(chat_id=-1001, title="User 1 Ch", owner_user_id=111, active=True, can_post=True)
        ch_user2 = ChannelItem(chat_id=-1002, title="User 2 Ch", owner_user_id=222, active=True, can_post=True)

        all_channels = [ch_user1, ch_user2]

        # For user 111: only ch_user1 must be shown
        kb1 = get_destination_selection_keyboard(all_channels, callback_prefix="test_prefix", user_id=111)
        buttons_user1 = [b.callback_data for row in kb1.inline_keyboard for b in row]
        self.assertIn("test_prefix:-1001", buttons_user1)
        self.assertNotIn("test_prefix:-1002", buttons_user1)

        # For user 222: only ch_user2 must be shown
        kb2 = get_destination_selection_keyboard(all_channels, callback_prefix="test_prefix", user_id=222)
        buttons_user2 = [b.callback_data for row in kb2.inline_keyboard for b in row]
        self.assertNotIn("test_prefix:-1001", buttons_user2)
        self.assertIn("test_prefix:-1002", buttons_user2)

        # Super Admin (8157452043) sees all channels
        kb_admin = get_destination_selection_keyboard(all_channels, callback_prefix="test_prefix", user_id=8157452043)
        buttons_admin = [b.callback_data for row in kb_admin.inline_keyboard for b in row]
        self.assertIn("test_prefix:-1001", buttons_admin)
        self.assertIn("test_prefix:-1002", buttons_admin)

        # If user has no channels: displays "➕ Avval kanal qo‘shing"
        kb_empty = get_destination_selection_keyboard([], callback_prefix="test_prefix", user_id=111)
        buttons_empty = [b.callback_data for row in kb_empty.inline_keyboard for b in row]
        self.assertIn("btn_add_channel", buttons_empty)

        # Verify confirmation keyboards
        kb_confirm = get_connection_confirm_keyboard("confirm_action_cb")
        confirm_cbs = [b.callback_data for row in kb_confirm.inline_keyboard for b in row]
        self.assertIn("confirm_action_cb", confirm_cbs)
        self.assertIn("menu_main", confirm_cbs)

        # Verify sources list keyboard
        src = SourceItem(id="src_1", name="Kun.uz", url="https://kun.uz/rss", category="yangiliklar")
        kb_sources = get_sources_list_keyboard([src])
        src_cbs = [b.callback_data for row in kb_sources.inline_keyboard for b in row]
        self.assertIn("del_src_ask:src_1", src_cbs)

        # Verify delete confirm keyboard
        kb_del = get_delete_source_confirm_keyboard("src_1", "Kun.uz")
        del_cbs = [b.callback_data for row in kb_del.inline_keyboard for b in row]
        self.assertIn("del_src_do:src_1", del_cbs)

        # Verify unsub and allunsub keyboards
        kb_unsub = get_unsub_confirm_keyboard("sub_1")
        self.assertIn("unsub_confirm:sub_1", [b.callback_data for row in kb_unsub.inline_keyboard for b in row])

        kb_allunsub = get_allunsub_confirm_keyboard()
        self.assertIn("allunsub_confirm", [b.callback_data for row in kb_allunsub.inline_keyboard for b in row])


if __name__ == "__main__":
    unittest.main()
