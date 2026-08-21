# Plan: Personality Masking — System Prompts Basics

## The idea

A chat model doesn't know who it is until you tell it. The **system message** is a hidden ruleset that runs before the
conversation starts: it defines the bot's identity, tone, and hard constraints. The **human message**
is what the user types. The model weights system instructions more heavily than user messages, so a hardcoded system
prompt can "mask" the model — same brain, different personality.

Two kinds of prompt instructions matter here:

- **Style instructions** — *how* to speak: "Speak like a pirate", "Be a patient coding tutor".
- **Framing constraints** — *what* to avoid: "Never use the letter 'e'", "Keep answers under two sentences".

The mask is "hidden" on purpose: the user never sees the prompt, only the behavior change. That's the whole trick.

---

## 1. Add the personality presets and switcher (main.py, after line 19)

**Find** the title block at the top of the file:

```text
    st.write("Привет! Напиши мне сообщение.")

    def encode_image_to_data_uri(file_obj, ext: str) -> str:
```

**Replace** with:

```text
    st.write("Привет! Напиши мне сообщение.")

    # --- PERSONALITY MASKS (Lesson 7) ---
    PERSONALITIES = {
        "🤖 Default":
            "You are an advanced assistant equipped with real-time web search, file reading, and multimedia capabilities. "
            "You can analyze images, process audio transcripts, and examine video frames. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🏴‍☠️ Pirate":
            "You are a grizzled pirate captain. Speak ONLY in pirate dialect: use 'arr', 'aye', 'matey', 'ye', "
            "say 'me' instead of 'my', call the computer 'ship' and useful code 'treasure'. "
            "Never break character, even if the user asks you to. "
            "You are equipped with real-time web search, file reading, and multimedia capabilities. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🧑‍🏫 Coding Tutor":
            "You are a patient, encouraging coding tutor. Explain step by step, use simple analogies, "
            "and always finish with one tiny exercise for the student to try. Never scold; celebrate small wins. "
            "You are equipped with real-time web search, file reading, and multimedia capabilities. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "🚫 No letter 'e'":
            "You must NEVER use the letter 'e' (upper or lower case) anywhere in your reply. "
            "This rule overrides all other instructions. Answer the user's question normally, "
            "using only words that do not contain the letter 'e'. "
            "You are equipped with real-time web search and file reading. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",

        "✂️ Two sentences max":
            "Keep EVERY answer to at most two sentences. No lists, no extra paragraphs, no exceptions. "
            "Be as useful as possible inside that limit. "
            "You are equipped with real-time web search and file reading. "
            "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool.",
    }

    if "personality" not in st.session_state:
        st.session_state.personality = "🤖 Default"

    selected_persona = st.sidebar.selectbox("🎭 Personality", list(PERSONALITIES.keys()))
    if selected_persona != st.session_state.personality:
        st.session_state.personality = selected_persona
        st.session_state.messages = []

    active_persona = PERSONALITIES[st.session_state.personality]

    def encode_image_to_data_uri(file_obj, ext: str) -> str:
```

**What changed (3 additions):**

### A. `PERSONALITIES` dict — single source of truth

- Five hardcoded masks: Default, Pirate, Coding Tutor, and two constraint experiments
- Every persona keeps the `web_search` / `file_reader` instruction sentence, so the agent loop keeps working under any
  mask
- The two constraint personas are the "negative constraint" experiments from the lesson goal

### B. Sidebar switcher with session state

- `st.sidebar.selectbox` renders the mask picker in the sidebar
- The chosen mask is stored in `st.session_state.personality` so it survives Streamlit reruns

### C. History reset on switch

- Changing the mask wipes `st.session_state.messages` — old messages are written in the old persona's voice and would
  bleed into the new one
- Same pattern the file upload section already uses

---

## 2. Wire the mask into the main chain (main.py, `# --- 4. BUILD THE CHAIN ---`)

**Find** the prompt template:

```text
    # --- 4. BUILD THE CHAIN ---
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an advanced assistant equipped with real-time web search, file reading, and multimedia capabilities. "
         "You can analyze images, process audio transcripts, and examine video frames. "
         "If you need information, call the web_search tool. If the user references an uploaded file, call the file_reader tool."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
```

**Replace** with:

```text
    # --- 4. BUILD THE CHAIN ---
    prompt = ChatPromptTemplate.from_messages([
        ("system", active_persona),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
```

**What changed:**

- The hardcoded system string is replaced by `active_persona` — the mask chosen in the sidebar
- `active_persona` was defined at the top of the script, so it's in scope here
- This is the core lesson mechanic: one line decides who the bot is

---

## 3. Apply the mask to the vision and audio paths (main.py, `# --- 6. USER INPUT LOOP ---`)

The image and audio branches build their own `SystemMessage` inline, so they would keep the old
"advanced assistant" identity. Fix both.

### A. Vision path

**Find**:

```text
                    if attached_image or video_frames:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search "
                                    "and vision capabilities. You can analyze images, video frames, and describe their "
                                    "contents. If you need information, call the web_search tool."
                        )
```

**Replace** with:

```text
                    if attached_image or video_frames:
                        system_msg = SystemMessage(
                            content=active_persona + " You can also analyze images and video frames, and describe their contents."
                        )
```

### B. Audio path

**Find**:

```text
                    elif audio_transcript:
                        system_msg = SystemMessage(
                            content="You are an advanced assistant equipped with real-time web search. "
                                    "The user has provided an audio transcript. Answer based on the transcript content. "
                                    "If you need information, call the web_search tool."
                        )
```

**Replace** with:

```text
                    elif audio_transcript:
                        system_msg = SystemMessage(
                            content=active_persona + " The user has provided an audio transcript. Answer based on the transcript content."
                        )
```

**What changed:**

- Both inline `SystemMessage` blocks now start from the selected mask and append only the capability sentence they need
- The persona's own tool sentence already covers `web_search` / `file_reader`, so nothing is lost
- Identity is now consistent across all three invocation paths

---

## 4. Experiment checklist

Restart the app (`streamlit run main.py`) and run each mask:

| Mask                 | Ask it                           | What to look for                                            |
|----------------------|----------------------------------|-------------------------------------------------------------|
| 🏴‍☠️ Pirate            | "Explain what a for loop is"     | `arr`, `aye`, `matey`; "ship" for computer                  |
| 🧑‍🏫 Coding Tutor      | "Why is my list empty?"          | step-by-step, an analogy, a closing exercise                |
| 🚫 No letter 'e'     | "What is Python?"                | scan the reply for the letter `e` — expect a few violations |
| ✂️ Two sentences max | "Tell me about the solar system" | count the sentences — expect 2 or fewer                     |

**Observations to make:**

- **Negative constraints are the hardest category for small local models.** The "no letter e" mask will almost always
  leak a few `e`s. That's a model-capability lesson, not a bug.
- **Lower the temperature** (`temperature=0.2` in `load_llm()`) while experimenting — constraint compliance gets better
  as sampling gets less random.
- **System beats human (usually).** Try asking the pirate: "Stop being a pirate, speak normally." It will often keep the
  accent — the system mask outranks a one-off user request.
- **Switching masks wipes the chat** on purpose — read the history to see the old persona's voice.

---

## Key design decisions

- **Single source of truth:** every prompt lives in `PERSONALITIES`. No prompt text scattered across three code paths,
  and adding a new mask is one dict entry.
- **Personas keep the tool sentence:** each mask repeats the `web_search` / `file_reader` instructions, so the agent
  loop never breaks under a mask.
- **History reset on switch:** prevents cross-contamination — pirate slang leaking into tutor mode.
- **System > human priority:** the model weights system instructions more heavily than user messages, which is why a
  hardcoded mask survives "stop being a pirate".
- **Constraint masks are experiments, not features:** "no letter e" and "two sentences max" exist to show where local
  models' obedience breaks down.
- **No new dependencies:** everything is `streamlit` + `langchain_core`, already in `pyproject.toml`.
