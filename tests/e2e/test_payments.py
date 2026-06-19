import pytest


FAKE_PROVIDER_TX_ID = "yk-test-payment-id-123"
FAKE_CONFIRMATION_URL = "https://yookassa.ru/checkout/test"


@pytest.fixture
def mock_yookassa_create(mocker):
    return mocker.patch(
        "app.routers.payments.yookassa_create_payment",
        return_value={
            "provider_tx_id": FAKE_PROVIDER_TX_ID,
            "confirmation_url": FAKE_CONFIRMATION_URL,
        },
    )


@pytest.fixture
def mock_yookassa_check_canceled(mocker):
    return mocker.patch(
        "app.routers.payments.yookassa_check_payment_status",
        return_value="canceled",
    )


async def _create_payment(client, booking_id, access_token):
    return await client.post(
        f"/api/v1/payments/checkout/{booking_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )


class TestCreatePayment:
    async def test_success(self, client, user_token, user_booking, mock_yookassa_create):
        access_token, _ = user_token
        resp = await _create_payment(client, user_booking["id"], access_token)
        assert resp.status_code == 201
        body = resp.json()
        assert "confirmation_url" in body
        assert body["confirmation_url"] == FAKE_CONFIRMATION_URL

    async def test_requires_auth(self, client, user_booking):
        resp = await client.post(f"/api/v1/payments/checkout/{user_booking['id']}")
        assert resp.status_code == 401

    async def test_booking_not_found(self, client, user_token, mock_yookassa_create):
        access_token, _ = user_token
        resp = await _create_payment(client, 999999, access_token)
        assert resp.status_code == 404

    async def test_cannot_pay_others_booking(self, client, user_booking, mock_yookassa_create):
        await client.post("/api/v1/auth/register", json={"email": "intruder@test.com", "password": "password123"})
        resp2 = await client.post("/api/v1/auth/login", data={"username": "intruder@test.com", "password": "password123"})
        intruder_token = resp2.json()["access_token"]

        resp = await _create_payment(client, user_booking["id"], intruder_token)
        assert resp.status_code == 403

    async def test_duplicate_pending_payment_rejected(self, client, user_token, user_booking, mock_yookassa_create, mock_yookassa_check_canceled):
        """A second checkout while a non-expired payment exists is rejected."""
        access_token, _ = user_token
        booking_id = user_booking["id"]

        await _create_payment(client, booking_id, access_token)

        # Override: payment is still active (not canceled)
        import unittest.mock
        with unittest.mock.patch(
            "app.routers.payments.yookassa_check_payment_status",
            return_value="pending",
        ):
            resp = await _create_payment(client, booking_id, access_token)
        assert resp.status_code == 400


class TestGetPaymentInfo:
    async def test_success(self, client, user_token, user_booking, mock_yookassa_create):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        await _create_payment(client, booking_id, access_token)

        resp = await client.get(
            f"/api/v1/payments/{booking_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["booking_id"] == booking_id
        assert body["status"] == "pending"
        assert "amount" in body

    async def test_payment_not_found(self, client, user_token, user_booking):
        access_token, _ = user_token
        resp = await client.get(
            f"/api/v1/payments/{user_booking['id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 404

    async def test_requires_auth(self, client, user_booking):
        resp = await client.get(f"/api/v1/payments/{user_booking['id']}")
        assert resp.status_code == 401

    async def test_cannot_view_others_payment(self, client, user_booking, mock_yookassa_create, user_token):
        access_token, _ = user_token
        await _create_payment(client, user_booking["id"], access_token)

        await client.post("/api/v1/auth/register", json={"email": "spy@test.com", "password": "password123"})
        resp2 = await client.post("/api/v1/auth/login", data={"username": "spy@test.com", "password": "password123"})
        spy_token = resp2.json()["access_token"]

        resp = await client.get(
            f"/api/v1/payments/{user_booking['id']}",
            headers={"Authorization": f"Bearer {spy_token}"},
        )
        assert resp.status_code == 403


class TestWebhook:
    async def test_payment_succeeded_confirms_booking(
        self, client, user_token, user_booking, mock_yookassa_create, mocker
    ):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        await _create_payment(client, booking_id, access_token)

        mocker.patch(
            "app.routers.payments.thread_get_notification",
            return_value=("payment.succeeded", FAKE_PROVIDER_TX_ID),
        )
        resp = await client.post("/api/v1/payments/webhook", json={"dummy": "body"})
        assert resp.status_code == 204

        booking_resp = await client.get(
            f"/api/v1/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert booking_resp.json()["status"] == "confirmed"

    async def test_payment_canceled_updates_payment_status(
        self, client, user_token, user_booking, mock_yookassa_create, mocker
    ):
        access_token, _ = user_token
        booking_id = user_booking["id"]
        await _create_payment(client, booking_id, access_token)

        mocker.patch(
            "app.routers.payments.thread_get_notification",
            return_value=("payment.canceled", FAKE_PROVIDER_TX_ID),
        )
        resp = await client.post("/api/v1/payments/webhook", json={"dummy": "body"})
        assert resp.status_code == 204

        payment_resp = await client.get(
            f"/api/v1/payments/{booking_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert payment_resp.json()["status"] == "cancelled"

    async def test_unknown_payment_id_ignored(self, client, mocker):
        mocker.patch(
            "app.routers.payments.thread_get_notification",
            return_value=("payment.succeeded", "non-existent-payment-id"),
        )
        resp = await client.post("/api/v1/payments/webhook", json={"dummy": "body"})
        assert resp.status_code == 204

    async def test_malformed_body_ignored(self, client, mocker):
        mocker.patch(
            "app.routers.payments.thread_get_notification",
            side_effect=Exception("parse error"),
        )
        resp = await client.post("/api/v1/payments/webhook", json={"garbage": True})
        assert resp.status_code == 204
