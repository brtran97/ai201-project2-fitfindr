"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    _STOP_WORDS = {"a", "an", "the", "in", "on", "of", "for", "and", "or", "to", "is", "it"}

    try:
        listings = load_listings()

        if max_price is not None:
            listings = [l for l in listings if l["price"] <= max_price]

        if size is not None:
            filter_size = size.strip().lower()
            def _size_matches(listing_size):
                segments = re.split(r'[/\s()]+', listing_size.lower())
                return any(filter_size == seg for seg in segments if seg)
            listings = [l for l in listings if _size_matches(l["size"])]

        keywords = [w for w in description.lower().split() if w not in _STOP_WORDS]

        scored = []
        for listing in listings:
            searchable = " ".join([
                listing["title"],
                listing["description"],
                " ".join(listing["style_tags"]),
                listing["category"],
                " ".join(listing["colors"]),
            ]).lower()
            score = sum(1 for kw in keywords if kw in searchable)
            if score > 0:
                scored.append((score, listing))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]
    except Exception:
        return []


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    try:
        client = _get_groq_client()

        item_details = (
            f"- Item: {new_item['title']}\n"
            f"- Description: {new_item['description']}\n"
            f"- Category: {new_item['category']}\n"
            f"- Style: {', '.join(new_item['style_tags'])}\n"
            f"- Colors: {', '.join(new_item['colors'])}\n"
            f"- Condition: {new_item['condition']}\n"
            f"- Price: ${new_item['price']}"
        )

        if not wardrobe.get("items"):
            system_msg = (
                "You are a personal stylist who specializes in secondhand fashion. "
                "The user is considering buying a thrifted item but hasn't told you what's "
                "in their wardrobe yet. Give general styling advice: what kinds of pieces "
                "pair well with this item, what vibes or aesthetics it works for, and "
                "2-3 specific outfit ideas using common wardrobe staples. "
                "Keep it conversational and brief — 3-5 sentences max, like a quick text from a stylish friend."
            )
            user_msg = (
                f"I'm considering this thrifted find:\n{item_details}\n\n"
                "I haven't shared my wardrobe yet. What are some ways I could style this piece?"
            )
        else:
            wardrobe_lines = []
            for item in wardrobe["items"]:
                line = (
                    f"- {item['name']} ({item['category']}) — "
                    f"colors: {', '.join(item['colors'])}, "
                    f"style: {', '.join(item['style_tags'])}"
                )
                if item.get("notes"):
                    line += f", notes: {item['notes']}"
                wardrobe_lines.append(line)
            formatted_wardrobe = "\n".join(wardrobe_lines)

            system_msg = (
                "You are a personal stylist who specializes in secondhand fashion. "
                "The user wants to know how a thrifted item would fit into their existing "
                "wardrobe. Suggest 1-2 complete outfits that pair the new item with "
                "SPECIFIC pieces from their wardrobe — reference each piece by name. "
                "Briefly explain why the combination works. "
                "Keep it conversational and concise — 3-5 sentences per outfit, no lengthy explanations."
            )
            user_msg = (
                f"I'm considering this thrifted find:\n{item_details}\n\n"
                f"Here's what I already have in my wardrobe:\n{formatted_wardrobe}\n\n"
                "Suggest 1-2 complete outfits pairing this new item with specific pieces from my wardrobe."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=256,
        )

        result = response.choices[0].message.content.strip()
        return result if result else "This item has great styling potential — try pairing it with basics in complementary colors."
    except Exception:
        return "I couldn't generate styling suggestions right now. Try again in a moment."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — no outfit suggestion was provided. Try running the search again."

    try:
        client = _get_groq_client()

        system_msg = (
            "You are a Gen-Z fashion content creator writing Instagram/TikTok captions "
            "for thrifted outfit posts. Write a 2-4 sentence caption that:\n"
            "- Feels casual and authentic (like a real OOTD post, not a product ad)\n"
            "- Mentions the item name, price, and platform naturally (once each)\n"
            "- Captures the outfit vibe with specific style language\n"
            "- Uses lowercase, might include an emoji or two, but isn't over-the-top\n"
            "Do NOT include hashtags. Just the caption text."
        )
        user_msg = (
            f"Write a caption for this outfit post:\n\n"
            f"The thrifted find: {new_item['title']}\n"
            f"- Price: ${new_item['price']}\n"
            f"- From: {new_item['platform']}\n"
            f"- Style: {', '.join(new_item['style_tags'])}\n"
            f"- Colors: {', '.join(new_item['colors'])}\n\n"
            f"The full outfit idea:\n{outfit}"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.9,
            max_tokens=128,
        )

        result = response.choices[0].message.content.strip()
        return result if result else "Found a great thrifted piece — check it out!"
    except Exception:
        return "Couldn't generate a fit card right now. Try again in a moment."
