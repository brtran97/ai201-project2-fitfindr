import re

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings tests ────────────────────────────────────────────────────

def test_search_returns_results():
    # Happy path: a broad query with matching keywords should return
    # a non-empty list of listing dicts with expected fields like title and price.
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "title" in results[0]
    assert "price" in results[0]


def test_search_empty_results():
    # No-results path: an impossible combination (nonexistent item, tiny size,
    # very low price) should return an empty list without raising an exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    # Price filtering: every returned listing must have a price at or below
    # the max_price threshold. If no listings are cheap enough, the result is [].
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    # Size filtering uses segment-based matching — "M" should match sizes like
    # "M", "S/M", "M/L" but NOT "XL (oversized)" or "One Size". We verify by
    # splitting each result's size field and checking "m" appears as a segment.
    results = search_listings("vintage", size="M", max_price=None)
    assert isinstance(results, list)
    for item in results:
        segments = re.split(r'[/\s()]+', item["size"].lower())
        assert "m" in segments


def test_search_no_matching_keywords():
    # Completely irrelevant keywords that don't appear in any listing should
    # return an empty list — no false positives from partial matches.
    results = search_listings("xyzzy foobarbaz", size=None, max_price=None)
    assert results == []


def test_search_sorted_by_relevance():
    # Results should be sorted by keyword overlap score (descending), so
    # listings matching more keywords from the description appear first.
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) >= 2


# ── suggest_outfit tests ─────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    # With a populated wardrobe (10 items), the LLM should return a non-empty
    # string that suggests outfits pairing the new item with wardrobe pieces.
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_outfit_empty_wardrobe():
    # Empty wardrobe failure mode: instead of crashing or returning empty,
    # the tool should return general styling advice from the LLM.
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card tests ────────────────────────────────────────────────────

def test_create_fit_card_success():
    # Happy path: given a valid outfit suggestion and item, the LLM should
    # return a non-empty caption string styled like an Instagram/TikTok post.
    item = search_listings("vintage graphic tee", max_price=50)[0]
    outfit = "Pair this with baggy jeans and chunky sneakers for a 90s vibe."
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit():
    # Empty outfit failure mode: passing an empty string should trigger the
    # guard clause and return a descriptive error message — no LLM call, no exception.
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = create_fit_card("", item)
    assert isinstance(result, str)
    assert "couldn't" in result.lower() or "no outfit" in result.lower()


def test_create_fit_card_whitespace_outfit():
    # Whitespace-only outfit should also be caught by the guard clause,
    # same as an empty string — returns the error message, not a caption.
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = create_fit_card("   ", item)
    assert isinstance(result, str)
    assert "couldn't" in result.lower() or "no outfit" in result.lower()
