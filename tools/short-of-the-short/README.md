# The Short of the Short

Paste a brain dump. Brevis, a talking AI aide, says "Hello, Jake. Here is the short of the short." and hands back the one line that matters, plus up to three specifics.

**Live page:** https://claude.ai/artifact/XbVqYqT4bffvQrEKY78N8b

The page is private to its owner until it is shared from the page's Share menu.

## Using it

1. Open the page in Claude.
2. Paste the brain dump, into the box or anywhere on the page. A paste of 8 words or more starts by itself. For anything typed, press **Get the short** (Cmd/Ctrl + Enter).
3. Read the highlighted line.

| Control | What it does |
| --- | --- |
| **Copy** | Puts the line and its points on the clipboard. |
| **Think harder** | Asks a more capable model for a second take. Slower: up to a minute. |
| **Stop** | Cancels a run in progress. Your text stays. |
| The name in "Hello, Jake." | Click it to change who Brevis greets. Remembered per browser. |
| Voice chip, top right | Turns the voice on or off, and stops it mid-sentence. |

Pasting again right after a result replaces the old dump. Click into the box first if you want to add to it instead.

## How it works

One file, `index.html`, published as a Claude artifact. No server, no API key, no build step.

- **The AI.** The artifact runtime's `sample` capability: each run is one call to Claude on the viewer's own Claude account. The first run asks the viewer for permission. A normal run uses the fastest model tier, so the answer starts within a second or two. Think harder uses the default tier.
- **The voice.** The `tts` capability speaks in a Claude voice. Claude does not offer it in Safari, Firefox, the mobile apps, or the Artifacts pane beside a Code session; there the page uses the browser's built-in voice, and stays silent if the browser has none.
- **The prompt** is `buildPrompt()`. It asks for one sentence of at most 20 words, then up to three `- ` lines. `parseShort()` reads the reply as it streams.

## Changing it

| To change | Edit in `index.html` |
| --- | --- |
| The default name | `value="Jake"` on the `#who` input |
| How short "short" is (20 words, 3 points) | `buildPrompt()` |
| How long a paste must be to start by itself | `AUTO_RUN_WORDS` |
| What Brevis says | `SAY` and `ERRORS` |
| Colors and type | the `:root` tokens at the top of the `<style>` block |

To put a change live, ask Claude in a Claude Code session to publish `tools/short-of-the-short/index.html` to the artifact URL above, with the `sample` and `tts` capabilities.

`index.html` is a page fragment with no `<html>` or `<body>` wrapper, because the artifact publisher adds one. Opened outside Claude it renders, says it can't reach Claude, and disables the button.

## Limits

- Viewers must be signed in to Claude. Each run counts against the viewer's own usage.
- The pasted text is sent to Claude. The page itself keeps only the name and the voice setting, in the browser. Claude's runtime may replay the answer to an identical paste for five minutes instead of asking again.
- One dump can be about 250,000 characters at most.
