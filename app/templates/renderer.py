from __future__ import annotations

import hashlib
import json

import httpx
from jinja2 import Environment, StrictUndefined, UndefinedError

from app.config import Settings


class TemplateRenderError(ValueError):
    pass


class MessageRenderer:
    def __init__(self, settings: Settings, cache_size: int = 1000):
        self.settings = settings
        self.env = Environment(undefined=StrictUndefined, autoescape=False)
        self.cache_size = cache_size
        self._cache: dict[str, str] = {}

    async def render(self, template_text: str, variables: dict, use_ai: bool = False) -> str:
        key = self._cache_key(template_text, variables, use_ai)
        if key in self._cache:
            return self._cache[key]
        try:
            rendered = self.env.from_string(template_text).render(**variables).strip()
        except UndefinedError as exc:
            raise TemplateRenderError(str(exc)) from exc
        if use_ai and self.settings.ai_provider and self.settings.ai_api_key:
            rendered = await self._vary_with_ai(rendered)
        if len(self._cache) >= self.cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = rendered
        return rendered

    async def _vary_with_ai(self, text: str) -> str:
        if self.settings.ai_provider.lower() != "openai":
            return text
        url = f"{self.settings.ai_api_base.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Slightly vary phrasing while preserving meaning. Keep it natural, concise, and non-pushy.",
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.7,
        }
        headers = {"Authorization": f"Bearer {self.settings.ai_api_key}"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _cache_key(template_text: str, variables: dict, use_ai: bool) -> str:
        raw = json.dumps({"template": template_text, "variables": variables, "ai": use_ai}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
