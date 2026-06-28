import time

from tests.api.test_uploads import JPEG_BYTES, PNG_BYTES


def _create_uploads(client) -> tuple[str, str]:
    person = client.post(
        "/api/v1/uploads/person",
        files={"file": ("selfie.jpg", JPEG_BYTES, "image/jpeg")},
    )
    garment = client.post(
        "/api/v1/uploads/garment",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )
    assert person.status_code == 201
    assert garment.status_code == 201
    return person.json()["upload_id"], garment.json()["upload_id"]


def test_create_job_returns_queued(client) -> None:
    person_id, garment_id = _create_uploads(client)
    response = client.post(
        "/api/v1/jobs",
        json={
            "person_upload_id": person_id,
            "garment_upload_id": garment_id,
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert "job_id" in body


def test_create_job_rejects_missing_upload(client) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={
            "person_upload_id": "00000000-0000-0000-0000-000000000099",
            "garment_upload_id": "00000000-0000-0000-0000-000000000098",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_get_job_completes_with_progress(client) -> None:
    person_id, garment_id = _create_uploads(client)
    created = client.post(
        "/api/v1/jobs",
        json={
            "person_upload_id": person_id,
            "garment_upload_id": garment_id,
        },
    )
    job_id = created.json()["job_id"]

    final = None
    deadline = time.time() + 5
    while time.time() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        final = response.json()
        if final["status"] == "completed":
            break
        assert final["status"] in ("queued", "processing")
        time.sleep(0.05)

    assert final is not None
    assert final["status"] == "completed"
    assert final["progress"] == 100
    assert final["stage"] is None


def test_get_job_not_found(client) -> None:
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


from app.db import SessionLocal, JobModel

def test_job_persisted_in_db(client, settings) -> None:
    person_id, garment_id = _create_uploads(client)
    created = client.post(
        "/api/v1/jobs",
        json={
            "person_upload_id": person_id,
            "garment_upload_id": garment_id,
        },
    )
    job_id = created.json()["job_id"]
    with SessionLocal() as db:
        job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
        assert job is not None


def test_health_ok(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_ok(client) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
