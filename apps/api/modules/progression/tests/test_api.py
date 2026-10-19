
from django.test import Client


def test_unauthenticated_requests():
    c = Client()
    for endpoint in ["/status/", "/articleship/", "/vault/", "/history/"]:
        res = c.get(f"/api/v1/progression{endpoint}")
        assert res.status_code == 401


def test_get_status_endpoint(api, enrolled):
    res = api.get("/status/")
    assert res.status_code == 200
    data = res.json_body
    assert data["active_enrollment"] is not None
    assert data["active_enrollment"]["level_code"] == "intermediate"
    assert "articleship" in data
    assert "exemptions" in data
    assert "available_transitions" in data
    assert len(data["current_groups"]) > 0


def test_execute_transition_api(api, enrolled, final_scheme):
    payload = {
        "transition_type": "full_level_pass",
        "target_level_code": "final",
        "paper_results": [
            {"subject_key": "taxation", "status": "passed", "marks": 62},
            {"subject_key": "corporate-laws", "status": "passed", "marks": 55},
        ],
        "articleship": {
            "is_active": True,
            "firm_name": "EY India",
            "weekday_minutes": 180,
            "weekend_minutes": 360,
            "study_mode": "active_study",
        },
    }
    res = api.post("/transition/", payload)
    assert res.status_code == 201
    data = res.json_body
    assert data["status"] == "applied"
    assert "transition_id" in data
    assert "new_enrollment_id" in data

    # Verify status reflects new level and articleship
    status_res = api.get("/status/")
    assert status_res.status_code == 200
    status_data = status_res.json_body
    assert status_data["active_enrollment"]["level_code"] == "final"
    assert status_data["articleship"]["firm_name"] == "EY India"
    assert len(status_data["exemptions"]) == 1


def test_transition_validation_error(api, enrolled):
    # Invalid transition type
    res = api.post("/transition/", {"transition_type": "invalid_type"})
    assert res.status_code == 400

    # Invalid marks (over 100)
    res = api.post(
        "/transition/",
        {
            "transition_type": "exemption_update",
            "paper_results": [{"subject_key": "taxation", "marks": 150}],
        },
    )
    assert res.status_code == 400


def test_rollback_transition_api(api, enrolled, final_scheme):
    trans_res = api.post(
        "/transition/",
        {
            "transition_type": "full_level_pass",
            "target_level_code": "final",
        },
    )
    assert trans_res.status_code == 201
    trans_id = trans_res.json_body["transition_id"]

    # Rollback
    rollback_res = api.post("/transition/rollback/", {"transition_id": trans_id})
    assert rollback_res.status_code == 200
    assert rollback_res.json_body["status"] == "reverted"

    # Status shows back on Intermediate
    status_res = api.get("/status/")
    assert status_res.json_body["active_enrollment"]["level_code"] == "intermediate"


def test_articleship_api(api, enrolled):
    # Update via PUT
    put_res = api.put(
        "/articleship/",
        {
            "is_active": True,
            "firm_name": "BDO International",
            "study_mode": "weekend_only",
            "weekday_minutes": 60,
            "weekend_minutes": 420,
        },
    )
    assert put_res.status_code == 200
    assert put_res.json_body["firm_name"] == "BDO International"
    assert put_res.json_body["study_mode"] == "weekend_only"

    # Read via GET
    get_res = api.get("/articleship/")
    assert get_res.status_code == 200
    assert get_res.json_body["firm_name"] == "BDO International"

    # Partial update via PATCH
    patch_res = api.patch("/articleship/", {"firm_name": "BDO India LLP"})
    assert patch_res.status_code == 200
    assert patch_res.json_body["firm_name"] == "BDO India LLP"


def test_vault_endpoint(api, enrolled, final_scheme):
    # Transition to archive current level
    api.post(
        "/transition/",
        {
            "transition_type": "full_level_pass",
            "target_level_code": "final",
        },
    )

    res = api.get("/vault/")
    assert res.status_code == 200
    enrollments = res.json_body["enrollments"]
    assert len(enrollments) >= 1
    assert enrollments[0]["level_code"] == "intermediate"
    assert len(enrollments[0]["subjects"]) > 0


def test_history_endpoint(api, enrolled, final_scheme):
    api.post(
        "/transition/",
        {
            "transition_type": "full_level_pass",
            "target_level_code": "final",
        },
    )

    res = api.get("/history/")
    assert res.status_code == 200
    history = res.json_body["history"]
    assert len(history) >= 1
    assert history[0]["transition_type"] == "full_level_pass"
    assert history[0]["can_rollback"] is True
