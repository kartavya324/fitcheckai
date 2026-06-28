# Minimal valid image magic bytes for validation tests
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 64


def test_upload_person_success(client) -> None:
    response = client.post(
        "/api/v1/uploads/person",
        files={"file": ("selfie.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "person"
    assert "upload_id" in body
    assert body["url"].startswith("http://testserver/files/uploads/persons/")
    assert body["url"].endswith(".jpg")


def test_upload_garment_success(client) -> None:
    response = client.post(
        "/api/v1/uploads/garment",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "garment"
    assert body["url"].startswith("http://testserver/files/uploads/garments/")
    assert body["url"].endswith(".png")


def test_upload_rejects_unsupported_type(client) -> None:
    response = client.post(
        "/api/v1/uploads/person",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_oversized_file(client, settings) -> None:
    oversized = JPEG_BYTES + (b"\x00" * (settings.max_upload_bytes + 1))
    response = client.post(
        "/api/v1/uploads/person",
        files={"file": ("big.jpg", oversized, "image/jpeg")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_rejects_magic_mismatch(client) -> None:
    response = client.post(
        "/api/v1/uploads/person",
        files={"file": ("fake.jpg", PNG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_upload_success(client) -> None:
    created = client.post(
        "/api/v1/uploads/person",
        files={"file": ("selfie.jpg", JPEG_BYTES, "image/jpeg")},
    )
    upload_id = created.json()["upload_id"]
    response = client.get(f"/api/v1/uploads/{upload_id}")
    assert response.status_code == 200
    assert response.json()["upload_id"] == upload_id
    assert response.json()["content_type"] == "image/jpeg"


def test_get_upload_not_found(client) -> None:
    response = client.get("/api/v1/uploads/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


def test_static_file_served(client) -> None:
    from urllib.parse import urlparse

    created = client.post(
        "/api/v1/uploads/person",
        files={"file": ("selfie.jpg", JPEG_BYTES, "image/jpeg")},
    )
    file_path = urlparse(created.json()["url"]).path
    response = client.get(file_path)
    assert response.status_code == 200
    assert response.content == JPEG_BYTES
