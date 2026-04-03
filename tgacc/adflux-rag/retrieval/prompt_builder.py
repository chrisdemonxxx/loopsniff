"""Build prompts with RAG context for the AdFlux Media AI responder."""

SYSTEM_PROMPT = """\
You are an AdFlux Media sales representative on Telegram. Your name is Alex.
You help media buyers and advertisers get premium agency ad accounts for restricted verticals.

Your style:
- Professional but friendly and concise (this is Telegram, not email)
- Knowledgeable about digital advertising, media buying, and ad platforms
- Consultative — ask questions to understand needs before pitching
- Never pushy — build trust first, close naturally

Your goal:
- Qualify the lead using BANT (Budget, Authority, Need, Timeline)
- Provide relevant information about AdFlux Media services
- Handle objections smoothly
- Guide toward a purchase decision

BANT Scoring:
- Budget: What's their monthly ad spend? ($1K-5K=low, $5K-20K=med, $20K+=high)
- Authority: Are they the decision maker?
- Need: Urgent (account banned) vs exploring?
- Timeline: This week=hot, next month=warm, someday=cold

Rules:
- NEVER make up information about the lead — only use what's provided in context
- If you don't know something, say so honestly
- Keep responses under 3-4 sentences for Telegram
- Use the lead's context to personalize your approach
- Reference their niche, platform experience, or pain points when relevant
"""


def build_outreach_prompt(
    lead_context: list[dict],
    knowledge_context: list[dict],
    conversation_history: list[dict] | None = None,
    lead_message: str = "",
) -> list[dict]:
    """Build a chat-style prompt list for Ollama / OpenAI-compatible API.

    Returns a list of {"role": ..., "content": ...} messages.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ── Inject lead context ───────────────────────────────────────────────
    if lead_context:
        lead_text = "\n\n".join(item["text"] for item in lead_context if item.get("text"))
        if lead_text.strip():
            messages.append({
                "role": "system",
                "content": (
                    "=== LEAD INTELLIGENCE (use to personalize, do NOT repeat verbatim) ===\n"
                    + lead_text
                ),
            })

    # ── Inject knowledge context ──────────────────────────────────────────
    if knowledge_context:
        kb_text = "\n\n".join(item["text"] for item in knowledge_context if item.get("text"))
        if kb_text.strip():
            messages.append({
                "role": "system",
                "content": (
                    "=== ADFLUX MEDIA KNOWLEDGE BASE ===\n" + kb_text
                ),
            })

    # ── Conversation history ──────────────────────────────────────────────
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # ── Current lead message ──────────────────────────────────────────────
    if lead_message:
        messages.append({"role": "user", "content": lead_message})

    return messages


def build_simple_prompt(query: str, knowledge_context: list[dict]) -> list[dict]:
    """Build a simpler prompt for knowledge-only queries (no lead context)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if knowledge_context:
        kb_text = "\n\n".join(item["text"] for item in knowledge_context if item.get("text"))
        if kb_text.strip():
            messages.append({
                "role": "system",
                "content": "=== ADFLUX MEDIA KNOWLEDGE BASE ===\n" + kb_text,
            })

    messages.append({"role": "user", "content": query})
    return messages
