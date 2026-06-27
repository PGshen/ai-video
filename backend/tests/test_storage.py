from unittest.mock import MagicMock, patch
import pytest


def test_upload_bytes_calls_put_object():
    mock_client = MagicMock()
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import upload_bytes
        from app.config import settings
        upload_bytes("test/key.mp3", b"audio-data", "audio/mpeg")
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["bucket_name"] == settings.MINIO_BUCKET
    assert call_kwargs["length"] == len(b"audio-data")
    # verify key passed
    assert call_kwargs["object_name"] == "test/key.mp3"


def test_get_presigned_url_returns_string():
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "http://minio/signed-url"
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import get_presigned_url
        url = get_presigned_url("video/proj/asset.mp4")
    assert url == "http://minio/signed-url"


def test_download_to_file_calls_fget_object(tmp_path):
    mock_client = MagicMock()
    with patch("app.storage._get_client", return_value=mock_client):
        from app.storage import download_to_file
        dest = str(tmp_path / "audio.mp3")
        download_to_file("audio/key.mp3", dest)
    mock_client.fget_object.assert_called_once()
    call_kwargs = mock_client.fget_object.call_args[1]
    assert call_kwargs["object_name"] == "audio/key.mp3"
    assert call_kwargs["file_path"] == dest
