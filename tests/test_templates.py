from __future__ import annotations

import pytest

from app.templates.renderer import MessageRenderer, TemplateRenderError


async def test_template_render_and_cache(settings):
    renderer = MessageRenderer(settings)
    text = await renderer.render("Hello {{ name }} from {{ niche }}", {"name": "Ann", "niche": "SaaS"})
    assert text == "Hello Ann from SaaS"
    assert await renderer.render("Hello {{ name }} from {{ niche }}", {"name": "Ann", "niche": "SaaS"}) == text


async def test_template_missing_variable(settings):
    renderer = MessageRenderer(settings)
    with pytest.raises(TemplateRenderError):
        await renderer.render("Hello {{ missing }}", {})
