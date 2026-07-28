from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.engines.ai.base import StyleLibraryAssistantResult
from app.models.prompt_component import PromptComponent
from app.models.style_template import StyleTemplate


def make_component(category: str = "color_scheme"):
    component = MagicMock(spec=PromptComponent)
    component.id = uuid4()
    component.category = category
    component.name = f"Test {category}"
    component.description = f"Description {category}"
    component.prompt_text = f"Prompt {category}"
    component.is_builtin = False
    return component


def make_template():
    template = MagicMock(spec=StyleTemplate)
    template.id = uuid4()
    template.name = "暖白科普"
    template.description = "适合知识解释"
    template.style_config = {"color_scheme": str(uuid4())}
    template.created_at = datetime.now(timezone.utc)
    template.updated_at = datetime.now(timezone.utc)
    return template


def test_create_style_template(client, auth_headers, mock_db):
    component = make_component()
    mock_db.get.return_value = component
    mock_db.add = MagicMock()
    now = datetime.now(timezone.utc)

    async def refresh_with_timestamps(template):
        template.created_at = now
        template.updated_at = now

    mock_db.refresh.side_effect = refresh_with_timestamps

    response = client.post(
        "/api/style-templates",
        headers=auth_headers,
        json={
            "name": "暖白科普",
            "description": "适合知识解释",
            "style_config": {"color_scheme": str(component.id)},
        },
    )

    assert response.status_code == 201
    created = mock_db.add.call_args.args[0]
    assert created.name == "暖白科普"
    assert created.style_config == {"color_scheme": str(component.id)}
    mock_db.commit.assert_awaited_once()


def test_create_style_template_rejects_category_mismatch(
    client, auth_headers, mock_db
):
    component = make_component(category="animation_style")
    mock_db.get.return_value = component

    response = client.post(
        "/api/style-templates",
        headers=auth_headers,
        json={
            "name": "错误组合",
            "style_config": {"color_scheme": str(component.id)},
        },
    )

    assert response.status_code == 422
    assert "category mismatch" in response.json()["detail"]
    mock_db.commit.assert_not_awaited()


def test_update_style_template(client, auth_headers, mock_db):
    template = make_template()
    component = make_component(category="narrative_style")
    mock_db.get.side_effect = [template, component]

    response = client.put(
        f"/api/style-templates/{template.id}",
        headers=auth_headers,
        json={
            "name": "节奏紧凑科普",
            "description": "",
            "style_config": {"narrative_style": str(component.id)},
        },
    )

    assert response.status_code == 200
    assert template.name == "节奏紧凑科普"
    assert template.description is None
    assert template.style_config == {"narrative_style": str(component.id)}


def test_delete_style_template(client, auth_headers, mock_db):
    template = make_template()
    mock_db.get.return_value = template

    response = client.delete(
        f"/api/style-templates/{template.id}", headers=auth_headers
    )

    assert response.status_code == 204
    mock_db.delete.assert_awaited_once_with(template)
    mock_db.commit.assert_awaited_once()


def test_style_template_requires_at_least_one_component(
    client, auth_headers, mock_db
):
    response = client.post(
        "/api/style-templates",
        headers=auth_headers,
        json={"name": "空模板", "style_config": {}},
    )

    assert response.status_code == 422


def make_library_payload():
    return {
        "name": "冷静科技纪录片",
        "description": "适合严谨的知识解释",
        "components": {
            category: {
                "name": f"冷静科技 · {category}",
                "description": f"{category} rules",
                "prompt_text": f"Complete prompt for {category}",
            }
            for category in (
                "narrative_style",
                "color_scheme",
                "animation_style",
                "exemplar",
            )
        },
    }


def test_create_style_library_creates_all_components_atomically(
    client, auth_headers, mock_db
):
    mock_db.add = MagicMock()
    now = datetime.now(timezone.utc)

    async def refresh_with_timestamps(template):
        template.created_at = now
        template.updated_at = now

    mock_db.refresh.side_effect = refresh_with_timestamps

    response = client.post(
        "/api/style-templates/library",
        headers=auth_headers,
        json=make_library_payload(),
    )

    assert response.status_code == 201
    added = [call.args[0] for call in mock_db.add.call_args_list]
    components = [item for item in added if isinstance(item, PromptComponent)]
    template = next(item for item in added if isinstance(item, StyleTemplate))
    assert {item.category for item in components} == {
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    }
    assert set(template.style_config) == {
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    }
    assert response.json()["styleConfig"] == template.style_config
    mock_db.commit.assert_awaited_once()


def test_style_library_assistant_updates_all_components(client, auth_headers):
    provider = MagicMock()
    provider.assist_style_library = AsyncMock(
        return_value=StyleLibraryAssistantResult(
            reply="已统一四个组件。",
            name="冷静科技纪录片",
            description="适合严谨知识解释",
            components={
                category: {
                    "name": f"科技 · {category}",
                    "description": f"{category} rules",
                    "prompt_text": f"Prompt for {category}",
                }
                for category in (
                    "narrative_style",
                    "color_scheme",
                    "animation_style",
                    "exemplar",
                )
            },
        )
    )

    with patch(
        "app.api.style_templates.get_ai_provider",
        return_value=provider,
    ):
        response = client.post(
            "/api/style-templates/assist",
            headers=auth_headers,
            json={
                "name": "",
                "description": "",
                "components": {},
                "conversation_history": [],
                "message": "生成一套冷静科技风格",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "冷静科技纪录片"
    assert set(payload["components"]) == {
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    }
    assert payload["components"]["color_scheme"]["promptText"] == (
        "Prompt for color_scheme"
    )
    provider.assist_style_library.assert_awaited_once()


def test_style_library_assistant_handles_oversized_provider_result(
    client, auth_headers
):
    provider = MagicMock()
    provider.assist_style_library = AsyncMock(
        return_value=StyleLibraryAssistantResult(
            reply="已生成。",
            name="超长风格库",
            description="测试响应边界",
            components={
                category: {
                    "name": category,
                    "description": "",
                    "prompt_text": (
                        "x" * 8001
                        if category == "exemplar"
                        else f"Prompt for {category}"
                    ),
                }
                for category in (
                    "narrative_style",
                    "color_scheme",
                    "animation_style",
                    "exemplar",
                )
            },
        )
    )

    with patch(
        "app.api.style_templates.get_ai_provider",
        return_value=provider,
    ):
        response = client.post(
            "/api/style-templates/assist",
            headers=auth_headers,
            json={
                "name": "",
                "description": "",
                "components": {},
                "conversation_history": [],
                "message": "生成风格库",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "AI style library assistant temporarily unavailable"
    )


def test_update_style_library_updates_exclusive_components(
    client, auth_headers, mock_db
):
    categories = (
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    )
    components = {category: make_component(category) for category in categories}
    template = make_template()
    template.style_config = {
        category: str(component.id)
        for category, component in components.items()
    }
    mock_db.get.side_effect = [
        template,
        *(components[category] for category in categories),
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = [template]
    mock_db.add = MagicMock()

    response = client.put(
        f"/api/style-templates/{template.id}/library",
        headers=auth_headers,
        json=make_library_payload(),
    )

    assert response.status_code == 200
    assert template.name == "冷静科技纪录片"
    assert components["color_scheme"].prompt_text == (
        "Complete prompt for color_scheme"
    )
    mock_db.add.assert_not_called()
    mock_db.commit.assert_awaited_once()
