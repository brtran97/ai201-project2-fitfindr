# FitFindr

A multi-tool AI agent that helps users find secondhand clothing, get outfit suggestions based on their wardrobe, and generate shareable fit cards. Built with Groq's `llama-3.3-70b-versatile` and Gradio.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Run tests:
```bash
pytest tests/ -v
```

---

## Tool Inventory

### 1. `search_listings(description, size, max_price)`

**Purpose:** Searches the 40-item mock listings dataset for items matching a text description, with optional size and price filters.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing what the user is looking for (e.g., "vintage graphic tee") |
| `size` | `str \| None` | Size to filter by, case-insensitive. "M" matches "S/M", "M/L", etc. `None` to skip |
| `max_price` | `float \| None` | Maximum price inclusive. `None` to skip |

**Returns:** A `list[dict]` of matching listings sorted by keyword relevance (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches.

### 2. `suggest_outfit(new_item, wardrobe)`

**Purpose:** Uses the LLM to suggest 1-2 complete outfits pairing a thrifted item with specific pieces from the user's wardrobe.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict from `search_listings` |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key containing wardrobe item dicts |

**Returns:** A `str` with outfit suggestions. References specific wardrobe pieces by name if the wardrobe has items; returns general styling advice if the wardrobe is empty.

### 3. `create_fit_card(outfit, new_item)`

**Purpose:** Uses the LLM to generate a short, shareable Instagram/TikTok-style caption for the outfit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Returns:** A `str` caption (2-4 sentences) that mentions the item name, price, and platform naturally. Returns a descriptive error message if `outfit` is empty.

---

## Planning Loop

The planning loop in `run_agent()` follows a conditional sequence — it does **not** call all three tools unconditionally:

1. **Parse the query** — sends the user's natural language input to the LLM, which extracts `description`, `size`, and `max_price` as structured JSON. If parsing fails, the agent sets `session["error"]` and returns early.

2. **Search listings** — calls `search_listings()` with the parsed parameters.
   - **If results are empty:** the agent sets `session["error"]` to a message suggesting the user broaden their search and **returns immediately** — it does not call `suggest_outfit` or `create_fit_card`.
   - **If results exist:** the agent selects the top result and continues.

3. **Suggest outfit** — calls `suggest_outfit()` with the selected item and the user's wardrobe. The tool handles the empty-wardrobe case internally, so the planning loop does not branch here.

4. **Create fit card** — calls `create_fit_card()` with the outfit suggestion and selected item.

5. **Return the session** with all output fields populated.

The agent's behavior differs based on what it receives. For example, querying "designer ballgown size XXS under $5" triggers the early return after step 2, while "vintage graphic tee under $30" flows through all three tools.

---

## State Management

All state lives in a single `session` dict created by `_new_session()` at the start of each interaction. Each tool reads its inputs from the session and writes its outputs back:

| Session Key | Set By | Used By |
|-------------|--------|---------|
| `query` | `_new_session` | LLM query parser |
| `parsed` | LLM parser -> `{description, size, max_price}` | `search_listings` |
| `search_results` | `search_listings` -> list of dicts | Planning loop (checks if empty) |
| `selected_item` | Planning loop -> `search_results[0]` | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `_new_session` | `suggest_outfit` |
| `outfit_suggestion` | `suggest_outfit` -> string | `create_fit_card` |
| `fit_card` | `create_fit_card` -> string | Final output |
| `error` | Planning loop (on failure) | Final output |

Data flows automatically between tools through the session — the user never re-enters information between steps. The item found by `search_listings` is the exact same dict passed into `suggest_outfit`, and the outfit string from `suggest_outfit` is passed directly into `create_fit_card`.

---

## Error Handling

Each tool handles its own failure mode gracefully:

### `search_listings` — no results found

If no listings match the query (e.g., "designer ballgown size XXS under $5"), the function returns an empty list `[]`. The planning loop detects this, sets `session["error"]` to "No listings found matching your search. Try broadening your description, removing the size filter, or increasing your budget," and returns the session early without calling the remaining tools.

**Test:** `test_search_empty_results` confirms that `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]` without raising an exception.

### `suggest_outfit` — empty wardrobe

If `wardrobe["items"]` is empty, the tool switches to a different LLM prompt that asks for general styling advice instead of wardrobe-specific pairings. It returns a useful suggestion string rather than crashing.

**Test:** `test_suggest_outfit_empty_wardrobe` confirms the tool returns a non-empty string when given `get_empty_wardrobe()`.

### `create_fit_card` — empty outfit input

If the `outfit` string is empty or whitespace-only, the tool returns the error message "Couldn't generate a fit card — no outfit suggestion was provided. Try running the search again." without calling the LLM or raising an exception.

**Test:** `test_create_fit_card_empty_outfit` and `test_create_fit_card_whitespace_outfit` confirm this behavior for both `""` and `"   "` inputs.

---

## Spec Reflection

**One way the spec helped:** Writing out the state management table in `planning.md` before coding made it clear exactly which session keys each tool needed to read and write. When implementing `run_agent()`, I could follow the table directly rather than figuring out the data flow on the fly. This prevented bugs like passing the wrong variable between tools.

**One way implementation diverged:** The spec originally didn't specify how the query would be parsed — it just said "extract description, size, and max_price." During implementation, I chose LLM-based parsing over regex because it handles natural language variation better (e.g., "nothing over thirty bucks" or "medium sized"). This added an extra LLM call but made the agent more robust to different phrasings, which was worth the tradeoff.

---

## AI Usage

### Instance 1: Implementing `search_listings`

I gave Claude Code the Tool 1 spec block from `planning.md` (inputs, return value, failure mode) along with the function stub and docstring from `tools.py`, and asked it to implement the function using `load_listings()` from the data loader. The generated code used segment-based size matching (`re.split` on `/`, spaces, and parens) to handle size formats like "S/M" and "XL (oversized)" — I reviewed this logic against the actual size values in `listings.json` to confirm it worked correctly (e.g., "M" matches "S/M" but not "One Size"). I also verified it included stop-word filtering for keyword scoring and returned `[]` on no matches. I tested with three queries before accepting: a happy-path match, a no-results query, and a price-filter-only query.

### Instance 2: Implementing the planning loop in `run_agent()`

I gave Claude Code the full Architecture diagram (Mermaid flowchart), Planning Loop section, and State Management table from `planning.md`, along with the `_new_session()` dict structure and `run_agent()` stub from `agent.py`. Before running the generated code, I checked that it: (1) branched on empty `search_results` and returned early instead of calling all tools unconditionally, (2) stored each tool's output in the correct session key matching the state management table, and (3) used `session["selected_item"]` (not a re-parsed value) as input to `suggest_outfit`. I tested with both built-in CLI test cases in `agent.py` — the happy-path query printed all three outputs, and the no-results query printed only the error message with `fit_card` remaining `None`.
