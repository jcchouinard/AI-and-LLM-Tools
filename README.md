# AI-and-LLM-Tools
Repository for all things related to AI search, LLMs, AI Agents and more

## Created by 
- [jcchouinard.com](https://www.jcchouinard.com/)
- [youtube.com/@jcchouinard](https://www.youtube.com/@jcchouinard)
- [x.com/ChouinardJC](https://x.com/ChouinardJC)
- [linkedin.com/in/jeanchristophechouinard](https://www.linkedin.com/in/jeanchristophechouinard)


## Start

```
$ python3 -m venv venv 
$ source venv/bin/activate 
$ pip install -r requirements.txt
```

## ChatGPT Tracking Chrome Extension
- Chrome Extension to track ChatGPT prompts and Query Fanouts ([extension](https://chromewebstore.google.com/detail/llm-inspector/fphgdjajimcchgblmjfbdjfbiapgnhei?authuser=0&hl=en-US), [article](https://jcchouinard.substack.com/p/chatgpt-extension-update-prompts))

## AI Agents

- `readme_generator.py`: AI agent that generates README.md file for a project (OpenAI API)

## Skills
Public-ready Claude Code skills live in [`skills/`](skills/). Copy a folder into `~/.claude/skills/` to install it.

- [`share-template`](skills/share-template/): turn a project and its Claude Code history into a PII-free, credential-free template zip (includes `scrub.py`)

## Templates
CLAUDE.md templates in [`templates/`](templates/). Copy one into a new project and tell Claude to read `CLAUDE.md` and recreate it.

- [`linkedin-carousel`](templates/linkedin-carousel/): screenshots and text to a LinkedIn carousel PDF, slides, thumbnail, and X post
- [`claude-usage-analyzer`](templates/claude-usage-analyzer/): analyze Claude Code session logs for cost, cache efficiency and tool usage, with a local dashboard
- [`system-design-explainer`](templates/system-design-explainer/): turn a codebase into a visual technical design (public and internal modes)

## Related
- [token-gate-tutorial](https://github.com/jcchouinard/token-gate-tutorial): cut Claude Code token cost by blocking full reads of big files with a PreToolUse hook and a Haiku subagent
