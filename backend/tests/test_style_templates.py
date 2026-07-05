from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.models.prompt_component import PromptComponent
from app.models.style_template import StyleTemplate


def make_component(category: str = "color_scheme"):
    component = MagicMock(spec=PromptComponent)
    component.id = uuid4()
    component.category = category
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
    component = make_component(category="pacing")
    mock_db.get.side_effect = [template, component]

    response = client.put(
        f"/api/style-templates/{template.id}",
        headers=auth_headers,
        json={
            "name": "节奏紧凑科普",
            "description": "",
            "style_config": {"pacing": str(component.id)},
        },
    )

    assert response.status_code == 200
    assert template.name == "节奏紧凑科普"
    assert template.description is None
    assert template.style_config == {"pacing": str(component.id)}


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
