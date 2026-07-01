from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4


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
