"""Example local LLM key config.

Copy this file to `app/mykey.py` and fill in your own key locally.
`app/mykey.py` is gitignored and must not be committed.
"""

LLM_SETTINGS = {
    "provider": "openai_compatible",
    "base_url": "https://api.deepseek.com",
    "api_key": "PASTE_YOUR_KEY_HERE",
    "model": "deepseek-chat",
    "timeout_seconds": 60,
    "temperature": 0.1,
    "max_tokens": 4096,
}
