"""
Handler for collecting human-curated posts from Central Content Channels.
Captures channel_post and edited_channel_post from channels registered in rss_storage.
Ensures zero alteration to original central posts and stores rich media attributes.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.types import Message

from app.services.rss_storage import rss_storage, CentralPoolChannel, PremiumPostItem

logger = logging.getLogger("anjurxbot.central_pool")

router = Router(name="central_pool")


def extract_media_details(message: Message) -> Dict[str, Any]:
    """Extracts media type, primary file_id, and album media_items from Telegram message."""
    res = {
        "media_type": "text",
        "media_file_id": None,
        "media_group_id": message.media_group_id,
        "text": message.text or message.caption or "",
        "media_items": [],
    }

    if message.photo:
        # Highest resolution is the last element
        res["media_type"] = "photo"
        res["media_file_id"] = message.photo[-1].file_id
        res["media_items"].append({
            "type": "photo",
            "file_id": message.photo[-1].file_id,
            "caption": message.caption or "",
        })
    elif message.video:
        res["media_type"] = "video"
        res["media_file_id"] = message.video.file_id
        res["media_items"].append({
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption or "",
        })
    elif message.document:
        res["media_type"] = "document"
        res["media_file_id"] = message.document.file_id
        res["media_items"].append({
            "type": "document",
            "file_id": message.document.file_id,
            "caption": message.caption or "",
        })
    elif message.audio:
        res["media_type"] = "audio"
        res["media_file_id"] = message.audio.file_id
        res["media_items"].append({
            "type": "audio",
            "file_id": message.audio.file_id,
            "caption": message.caption or "",
        })
    elif message.voice:
        res["media_type"] = "voice"
        res["media_file_id"] = message.voice.file_id
    elif message.animation:
        res["media_type"] = "animation"
        res["media_file_id"] = message.animation.file_id
        res["media_items"].append({
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": message.caption or "",
        })

    return res


CENTRAL_POST_BASE_CHAT_ID = -1004373620008

@router.channel_post()
async def on_channel_post(message: Message, bot: Bot):
    """Listens for new posts in central content channels."""
    chat = message.chat
    if not chat or chat.type not in ("channel", "supergroup"):
        return

    # Check if this channel is the Central Post Base (@anjurxpostbaza) or registered Central Channel
    is_central = chat.id == CENTRAL_POST_BASE_CHAT_ID
    if not is_central:
        cchan = await rss_storage.get_central_channel(chat.id)
        if cchan and cchan.active:
            is_central = True

    if not is_central:
        return

    logger.info(f"[POST_BASE] Received post: sourceChatId={chat.id} messageId={message.message_id}")

    media_data = extract_media_details(message)
    post_id = f"prem_{chat.id}_{message.message_id}"

    # Handle Media Group (Album) grouping
    if message.media_group_id:
        existing = await rss_storage.get_premium_post(post_id)
        if not existing:
            # Check if there is already an existing leader for this media_group_id
            all_posts = await rss_storage.get_all_premium_posts()
            group_lead = next(
                (p for p in all_posts if p.central_chat_id == chat.id and p.media_group_id == message.media_group_id),
                None
            )
            if group_lead:
                # Append this item to the existing group
                new_item = media_data["media_items"][0] if media_data["media_items"] else {
                    "type": media_data["media_type"],
                    "file_id": media_data["media_file_id"],
                    "caption": message.caption or "",
                }
                group_lead.media_items.append(new_item)
                if not group_lead.text and media_data["text"]:
                    group_lead.text = media_data["text"]
                group_lead.media_type = "media_group"
                group_lead.updated_at = datetime.utcnow().isoformat()
                await rss_storage.save_premium_post(group_lead)
                logger.info(f"Appended media item to album group {group_lead.id} ({len(group_lead.media_items)} items)")
                return

    # Author info (for internal record only, never broadcasted)
    author_id = message.from_user.id if message.from_user else None
    author_name = message.from_user.full_name if message.from_user else (message.author_signature or None)

    post = PremiumPostItem(
        id=post_id,
        central_chat_id=chat.id,
        central_message_id=message.message_id,
        media_type=media_data["media_type"],
        text=media_data["text"],
        media_file_id=media_data["media_file_id"],
        media_group_id=media_data["media_group_id"],
        media_items=media_data["media_items"],
        author_id=author_id,
        author_name=author_name,
        status="ready",
        delivered_count=0,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
    )

    await rss_storage.save_premium_post(post)
    logger.info(f"[POST_BASE] Saved to Firestore: postId={post.id}")
    logger.info(f"Collected new premium post {post_id} ({post.media_type}) from central channel '{chat.title}'")


@router.edited_channel_post()
async def on_edited_channel_post(message: Message, bot: Bot):
    """Updates post in pool if edited in central channel before delivery."""
    chat = message.chat
    if not chat:
        return

    cchan = await rss_storage.get_central_channel(chat.id)
    if not cchan:
        return

    post_id = f"prem_{chat.id}_{message.message_id}"
    post = await rss_storage.get_premium_post(post_id)
    if not post:
        return

    media_data = extract_media_details(message)
    post.text = media_data["text"]
    if media_data["media_file_id"]:
        post.media_file_id = media_data["media_file_id"]
        post.media_type = media_data["media_type"]
    post.updated_at = datetime.utcnow().isoformat()

    await rss_storage.save_premium_post(post)
    logger.info(f"Updated edited premium post {post_id} from central channel '{chat.title}'")
