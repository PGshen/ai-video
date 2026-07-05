import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.models.ai_call_record import AICallRecord


def make_record() -> AICallRecord:
    now = datetime.now(timezone.utc)
    return AICallRecord(
        id=uuid.uuid4(),
        provider="deepseek",
        model="deepseek-test",
        business="narrative_generation",
        request_type="chat",
        status="succeeded",
        input={"messages": [{"role": "user", "content": "hello"}]},
        output="world",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cached_tokens=2,
        reasoning_tokens=1,
        input_cost=Decimal("0.00001"),
        output_cost=Decimal("0.00002"),
        total_cost=Decimal("0.00003"),
        currency="USD",
        duration_ms=321,
        started_at=now,
        completed_at=now,
        created_at=now,
    )


def test_list_ai_call_records_returns_summary(
    client, auth_headers, mock_db
):
    record = make_record()
    records_result = MagicMock()
    records_result.scalars.return_value.all.return_value = [record]
    stats_result = MagicMock()
    stats_result.one.return_value = (1, 1, 0, 15, Decimal("0.00003"), 321)
    mock_db.execute.side_effect = [records_result, stats_result]

    response = client.get("/api/ai-call-records", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["summary"]["totalTokens"] == 15
    assert body["items"][0]["model"] == "deepseek-test"
    assert body["items"][0]["business"] == "narrative_generation"
    assert body["items"][0]["outputPreview"] == "world"


def test_get_ai_call_record_returns_full_payload(
    client, auth_headers, mock_db
):
    record = make_record()
    mock_db.get.return_value = record

    response = client.get(
        f"/api/ai-call-records/{record.id}", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["input"]["messages"][0]["content"] == "hello"
    assert body["output"] == "world"
    assert body["usage"]["completion_tokens"] == 5
