from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.engines.ai.base import StyleAssistantResult


def make_component(*, is_builtin: bool = False):
    component = MagicMock()
    component.id = uuid4()
    component.category = "color_scheme"
    component.name = "Test component"
    component.description = "Test description"
    component.prompt_text = "Test prompt"
    component.is_builtin = is_builtin
    component.created_by = None
    component.created_at = datetime.now(timezone.utc)
    component.updated_at = datetime.now(timezone.utc)
    return component


def test_update_prompt_component_category(client, auth_headers, mock_db):
    component = make_component()
    mock_db.get.return_value = component

    response = client.put(
        f"/api/prompt-components/{component.id}",
        headers=auth_headers,
        json={"category": "animation_style"},
    )

    assert response.status_code == 200
    assert response.json()["category"] == "animation_style"
    assert component.category == "animation_style"
    mock_db.commit.assert_awaited_once()


def test_builtin_prompt_component_category_cannot_be_updated(client, auth_headers, mock_db):
    component = make_component(is_builtin=True)
    mock_db.get.return_value = component

    response = client.put(
        f"/api/prompt-components/{component.id}",
        headers=auth_headers,
        json={"category": "animation_style"},
    )

    assert response.status_code == 403
    assert component.category == "color_scheme"
    mock_db.commit.assert_not_awaited()


def test_style_assistant_updates_prompt_draft(client, auth_headers):
    provider = MagicMock()
    provider.assist_style_prompt = AsyncMock(
        return_value=StyleAssistantResult(
            reply="我加强了配色约束。",
            name="冷静科技蓝",
            description="适合科技知识视频",
            prompt_text="背景使用深蓝，重点信息仅使用青色。",
        )
    )

    with patch(
        "app.api.prompt_components.get_ai_provider",
        return_value=provider,
    ):
        response = client.post(
            "/api/prompt-components/assist",
            headers=auth_headers,
            json={
                "category": "color_scheme",
                "name": "",
                "description": "",
                "prompt_text": "",
                "conversation_history": [],
                "message": "想要冷静的科技感",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "我加强了配色约束。",
        "name": "冷静科技蓝",
        "description": "适合科技知识视频",
        "promptText": "背景使用深蓝，重点信息仅使用青色。",
    }
    provider.assist_style_prompt.assert_awaited_once()


def test_style_assistant_rejects_empty_message(client, auth_headers):
    response = client.post(
        "/api/prompt-components/assist",
        headers=auth_headers,
        json={
            "category": "pacing",
            "message": "",
        },
    )

    assert response.status_code == 422
