# Plan: Custom Look — HTML & CSS Injection

## The idea

Every web app is built from two layers: **HTML** (the structure — a tree of boxes and text that the
browser lays out) and **CSS** (the style — the rules that say which box gets which color, border,
and font). Streamlit already writes both for us, which is why every Streamlit app looks the same
gray. In this lesson we reach into that layer and inject **our own CSS** to give the chatbot a face
of its own.

Four concepts do the work:

- **HTML structure** — the browser builds a nested tree of elements (`<div>` inside `<section>`
  inside `<body>`). To style something, you first need to *find* it in that tree.
- **CSS style rules** — a rule is `selector { property: value; }`. The **selector** picks the
  element(s); the **properties** change how they look.
- **The cascade** — when several rules target the same element, the browser merges them by
  *specificity* and *order*. More specific selectors win — that's how a short stylesheet overrides
  Streamlit's defaults.
- **`unsafe_allow_html` safety** — this flag tells Streamlit "render this raw HTML, don't escape
  it." It is powerful and dangerous: only ever inject CSS *you* wrote. Piping untrusted text
  (user input, web results) through it is how XSS attacks happen.

The one line that powers the whole lesson:

```python
st.markdown("<style>...our css...</style>", unsafe_allow_html=True)
```

---

## 1. Add the THEMES dict, the switcher, and the injection (main.py, after line 20)

**Find** the title block at the top of the file:

```python
    st.write("Привет! Напиши мне сообщение.")

    # --- PERSONALITY MASKS (Lesson 7) ---
```

**Replace** with:

```python
    st.write("Привет! Напиши мне сообщение.")

    # --- CUSTOM THEMES (Lesson 9) ---
    THEMES = {
        "🌌 Neon Space": """
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&display=swap');
            section[data-testid="stMain"] { background: radial-gradient(ellipse at top, #101035 0%, #03030f 70%); }
            section[data-testid="stSidebar"] { background: #070720; }
            div[data-testid="stChatMessage"] {
                border: 1px solid #00e5ff;
                border-radius: 14px;
                box-shadow: 0 0 12px rgba(0, 229, 255, 0.55), inset 0 0 8px rgba(0, 229, 255, 0.15);
                background: rgba(10, 10, 46, 0.85);
            }
            h1 { font-family: 'Orbitron', monospace; color: #00e5ff; text-shadow: 0 0 10px rgba(0, 229, 255, 0.8); }
            div[data-testid="stChatInput"] { border: 1px solid #00e5ff; border-radius: 12px; box-shadow: 0 0 8px rgba(0, 229, 255, 0.4); }
        """,

        "👾 Pixel Arcade": """
            @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
            section[data-testid="stMain"] { background: #1a1a2e; }
            section[data-testid="stSidebar"] { background: #14142a; }
            div[data-testid="stChatMessage"] {
                border: 3px solid #ffcc00;
                border-radius: 0;
                box-shadow: 5px 5px 0 #ff00aa;
                background: #22223a;
                font-family: 'Press Start 2P', monospace;
                font-size: 11px;
                line-height: 2;
            }
            h1 { font-family: 'Press Start 2P', monospace; color: #ffcc00; font-size: 1.4rem; }
            div[data-testid="stChatInput"] { border: 3px solid #ffcc00; border-radius: 0; box-shadow: 4px 4px 0 #ff00aa; }
        """,

        "🌊 Ocean Breeze": """
            section[data-testid="stMain"] { background: linear-gradient(160deg, #e0f7fa 0%, #b3e5fc 100%); }
            section[data-testid="stSidebar"] { background: #e1f5fe; }
            div[data-testid="stChatMessage"] {
                border: 2px solid #4fc3f7;
                border-radius: 20px;
                box-shadow: 0 4px 14px rgba(79, 195, 247, 0.35);
                background: #ffffff;
                font-family: 'Comic Sans MS', 'Comic Neue', cursive;
            }
            h1 { font-family: 'Comic Sans MS', 'Comic Neue', cursive; color: #0277bd; }
            div[data-testid="stChatInput"] { border: 2px solid #4fc3f7; border-radius: 16px; }
        """,
    }

    if "theme" not in st.session_state:
        st.session_state.theme = "🌌 Neon Space"

    selected_theme = st.sidebar.selectbox("🎨 Theme", list(THEMES.keys()))
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme

    active_css = THEMES[st.session_state.theme]
    st.markdown(f"<style>{active_css}</style>", unsafe_allow_html=True)

    # --- PERSONALITY MASKS (Lesson 7) ---
```

**What changed (3 additions):**

### A. `THEMES` dict — one entry per look

- Three ready-made CSS strings. Each one is a complete stylesheet: an optional `@import` line that
  pulls a web font from Google Fonts, then rules for the main background, the sidebar, the chat
  bubbles, the title, and the input box.
- Adding a new look is one dict entry — the switcher picks it up automatically, no other code
  changes.

### B. Sidebar switcher with session state

- `st.sidebar.selectbox("🎨 Theme", ...)` renders the picker, stored in `st.session_state.theme`
  so it survives Streamlit reruns (the same pattern as the Lesson 7 personality switcher).
- Unlike a personality change, switching themes does **not** clear the chat — the conversation is
  independent of the skin.

### C. The injection line

- `st.markdown(f"<style>{active_css}</style>", unsafe_allow_html=True)` wraps the CSS in a
  `<style>` tag and tells Streamlit to render it as raw HTML. The browser applies the rules to the
  whole page, and the generic gray Streamlit look disappears.

---

## 2. How the CSS finds things (the selectors)

Streamlit gives its elements stable `data-testid` attributes. Those are the handles we grab:

| Selector | What it is |
|---|---|
| `section[data-testid="stMain"]` | the main content area (the big background) |
| `section[data-testid="stSidebar"]` | the left sidebar |
| `div[data-testid="stChatMessage"]` | every chat bubble (user + assistant) |
| `div[data-testid="stChatInput"]` | the text box you type into |
| `h1` | the page title |

A rule reads left-to-right: *find* the element on the left, *change* it with the properties on the
right.

```css
div[data-testid="stChatMessage"] {
    border: 1px solid #00e5ff;      /* a thin cyan edge around every bubble */
    border-radius: 14px;            /* round the corners */
    box-shadow: 0 0 12px #00e5ff;   /* the "glow" — a soft colored halo */
    background: #0a0a2e;            /* the bubble's fill */
}
```

**The glow** is just `box-shadow` with no offset and a blur (`0 0 12px`). Bigger blur = bigger
halo. That single property is the entire "neon" trick — no images, no JavaScript.

**Fonts** come from two places:

- `@import url('https://fonts.googleapis.com/css2?family=...')` downloads a web font (Orbitron,
  Press Start 2P) from Google's font library.
- `'Comic Sans MS'` is a font already installed on most computers — no download needed.
- The `font-family` list is a *fallback chain*: the browser uses the first font it has and skips to
  the next one if it doesn't.

---

## 3. The cascade — why our rules beat Streamlit's

Streamlit ships its own CSS. When our rules and Streamlit's rules target the same element, the
browser runs the **cascade**:

1. **Specificity** — a selector that names more things wins. `div[data-testid="stChatMessage"]`
   (tag + attribute) is more specific than Streamlit's plain class rule, so ours wins.
2. **Order** — if specificity is equal, the rule that appears *later* in the document wins. Our
   `<style>` is injected into the page, so it lands after Streamlit's defaults.

That's why a short stylesheet can completely re-skin the app without touching Streamlit's code.

---

## 4. Security — `unsafe_allow_html` is a loaded gun

`unsafe_allow_html=True` means "trust this string and render it as real HTML." That is exactly what
we want for CSS we wrote ourselves. It is exactly what we **never** want for text we did not write.

- ✅ Safe: `st.markdown(f"<style>{THEMES[theme]}</style>", unsafe_allow_html=True)` — the CSS is
  hardcoded in our own file.
- ❌ Dangerous: `st.markdown(user_input, unsafe_allow_html=True)` — a visitor could type
  `<script>steal(cookies)</script>` and the browser would *execute* it. That's a
  **cross-site scripting (XSS)** attack.

**The rule to keep for life as a developer:** the `unsafe_allow_html` flag is only for content you
control. User input and web results stay escaped.

---

## Experiment checklist

Restart the app (`streamlit run main.py`) and walk through:

| Step | What to look for |
|---|---|
| Right-click any chat bubble → **Inspect** | DevTools opens; find `data-testid="stChatMessage"` in the HTML tree |
| Switch to 🌌 Neon Space | dark background, cyan glowing bubbles, Orbitron title |
| Switch to 👾 Pixel Arcade | blocky pixel font, square yellow/magenta bubbles |
| Switch to 🌊 Ocean Breeze | light-blue gradient, Comic Sans, soft rounded bubbles |
| Add a 4th theme | one new dict entry — it appears in the switcher instantly |
| Delete a `box-shadow` line from a theme | the glow vanishes — that line *was* the neon |

**Observations to make:**

- **The skin is separate from the brain.** Switch themes mid-conversation — the messages and the
  personality are untouched. Style and logic never mix.
- **Google Fonts needs the internet.** Block the network (or comment out the `@import`) and the
  pixel font falls back to `monospace` — the fallback chain doing its job.
- **`data-testid` is the stable handle.** Streamlit's other class names are random hashes
  (`.st-emotion-cache-xxxx`) that change between versions — never target those.

---

## Key design decisions

- **`data-testid` selectors, not hashed classes:** Streamlit's generated class names are random and
  change on upgrade. `data-testid` attributes are stable and readable.
- **Three themes, one dict:** each look is a self-contained CSS string; adding a theme is a single
  entry, and the switcher needs no changes.
- **Theme ≠ personality:** switching themes keeps the chat (unlike Lesson 7), because the visual
  skin and the conversation are independent.
- **Glow = `box-shadow`:** one property does the whole "neon" effect — no images, no JavaScript.
- **`unsafe_allow_html` only for self-written CSS:** the lesson bakes in the XSS rule so the flag is
  never misused later.
- **No new dependencies:** pure `streamlit` + a CSS string; web fonts load in the browser, not
  Python.
