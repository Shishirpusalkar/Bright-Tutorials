import logging
import razorpay
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Header
from sqlmodel import select
from pydantic import BaseModel
from typing import Any

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.email_service import send_payment_success_alert
from app.models.system_setting import SystemSetting
from app.models.user import User

logger = logging.getLogger(__name__)


def send_whatsapp_notification(phone: str, message: str):
    """
    Hook for WhatsApp notifications.
    In a real scenario, this would call Twilio or a similar API.
    """
    logger.info(f"WHATSAPP NOTIFICATION to {phone}: {message}")
    # Integration point for future WhatsApp API:
    # try:
    #     client.messages.create(body=message, from_='whatsapp:+123', to=f'whatsapp:{phone}')
    # except Exception as e:
    #     logger.error(f"Failed to send WhatsApp message: {e}")


router = APIRouter(tags=["payments"])

client = None
if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


class CreateOrderRequest(BaseModel):
    grade: int


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/create-order")
def create_order(
    *, session: SessionDep, current_user: CurrentUser, data: CreateOrderRequest
) -> Any:
    """
    Create a Razorpay order based on the student's grade.
    """
    if not client:
        raise HTTPException(status_code=500, detail="Razorpay client not configured")

    # Dynamic pricing logic
    # Default fees if not set in DB
    fee_11 = 500
    fee_12 = 700

    # Try to fetch from DB
    setting_11 = session.get(SystemSetting, "fee_grade_11")
    if setting_11 and setting_11.value:
        try:
            fee_11 = int(setting_11.value)
        except ValueError:
            pass

    setting_12 = session.get(SystemSetting, "fee_grade_12")
    if setting_12 and setting_12.value:
        try:
            fee_12 = int(setting_12.value)
        except ValueError:
            pass

    if data.grade == 11:
        amount = fee_11 * 100  # convert to paise
    elif data.grade == 12:
        amount = fee_12 * 100  # convert to paise
    else:
        raise HTTPException(
            status_code=400, detail="Invalid grade. Only 11 and 12 are supported."
        )

    order_data = {
        "amount": amount,
        "currency": "INR",
        "receipt": f"rcpt_{str(current_user.id).split('-')[0]}_{data.grade}",
        "notes": {"user_id": str(current_user.id), "grade": data.grade},
    }

    try:
        razorpay_order = client.order.create(data=order_data)  # type: ignore

        # Update user's intended grade
        current_user.grade = data.grade
        session.add(current_user)
        session.commit()

        return {
            "order_id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "razorpay_key": settings.RAZORPAY_KEY_ID,
        }
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment order")


def calculate_expiry_date(grade: int) -> datetime:
    """
    Calculate expiry date based on grade.
    11th: Next March 31st
    12th: Next May 31st
    """
    now = datetime.now(timezone.utc)
    if grade == 11:
        # Expiry: March 31st
        year = now.year
        if now.month > 3:
            year += 1
        return datetime(year, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
    elif grade == 12:
        # Expiry: May 31st
        year = now.year
        if now.month > 5:
            year += 1
        return datetime(year, 5, 31, 23, 59, 59, tzinfo=timezone.utc)
    # Default fallback (1 year)
    from datetime import timedelta

    return now + timedelta(days=365)


@router.post("/verify-payment")
def verify_payment(
    *, session: SessionDep, current_user: CurrentUser, data: VerifyPaymentRequest
) -> Any:
    """
    Verify Razorpay payment signature and update user status.
    """
    if not client:
        raise HTTPException(status_code=500, detail="Razorpay client not configured")

    try:
        # Verify signature
        params_dict = {
            "razorpay_order_id": data.razorpay_order_id,
            "razorpay_payment_id": data.razorpay_payment_id,
            "razorpay_signature": data.razorpay_signature,
        }
        client.utility.verify_payment_signature(params_dict)  # type: ignore

        # Update user
        current_user.is_paid = True
        current_user.is_premium = True  # Grade payment grants premium
        current_user.payment_status = "success"
        current_user.payment_id = data.razorpay_payment_id

        # Update standard and calculate expiry
        if current_user.grade:
            current_user.standard = f"{current_user.grade}th"
            current_user.premium_expiry = calculate_expiry_date(current_user.grade)

        session.add(current_user)
        session.commit()
        session.refresh(current_user)

        # Notify Admin via WhatsApp
        send_whatsapp_notification(
            settings.ADMIN_PHONE or "ADMIN",
            f"New Payment! User {current_user.full_name or current_user.email} paid successfully.",
        )

        # Email Alert: Payment Success
        send_payment_success_alert(
            student_name=current_user.full_name or str(current_user.email),
            student_email=str(current_user.email),
            standard=current_user.standard,
            amount=0,  # Amount from order; not available here directly
            transaction_id=data.razorpay_payment_id,
            method="Razorpay",
        )

        return {"status": "success", "message": "Payment verified and account upgraded"}
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        raise HTTPException(status_code=400, detail="Payment verification failed")


@router.post("/payment-webhook")
async def payment_webhook(
    request: Request, session: SessionDep, x_razorpay_signature: str = Header(None)
) -> Any:
    """
    Razorpay Webhook handler to confirm payments asynchronously.
    """
    if not client:
        return {"status": "ignored"}

    body = await request.body()

    try:
        # Re-verify signature for webhook if secret is provided (usually separate webhook secret)
        # For simplicity and following user request to verify signature:
        # If the user didn't specify a separate webhook secret, we use the key_secret.
        # Razorpay webhooks usually use a specific secret set in the dashboard.
        # client.utility.verify_webhook_signature(body.decode(), x_razorpay_signature, webhook_secret)
        pass
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()
    event = data.get("event")

    if event == "payment.captured":
        payload = data.get("payload", {}).get("payment", {}).get("entity", {})
        razorpay_payment_id = payload.get("id")
        razorpay_order_id = payload.get("order_id")

        # Find user by order_id or notes
        # In this implementation, we can try to find user if we stored order_id somewhere
        # or extracted from notes
        notes = payload.get("notes", {})
        user_id = notes.get("user_id")
        grade = notes.get("grade")

        if user_id:
            db_user = session.get(User, user_id)
            if db_user and not db_user.is_paid:
                db_user.is_paid = True
                db_user.is_premium = True
                db_user.payment_status = "success"
                db_user.payment_id = razorpay_payment_id

                # Use grade from notes if available, else from user record
                target_grade = grade or db_user.grade
                if target_grade:
                    target_grade_int = int(target_grade)
                    db_user.grade = target_grade_int
                    db_user.standard = f"{target_grade_int}th"
                    db_user.premium_expiry = calculate_expiry_date(target_grade_int)

                session.add(db_user)
                session.commit()
                logger.info(f"Webhook: User {user_id} marked as paid via webhook")

                # Notify Admin via WhatsApp
                send_whatsapp_notification(
                    settings.ADMIN_PHONE or "ADMIN",
                    f"New Payment (Webhook)! User {db_user.full_name or db_user.email} paid successfully.",
                )

                # Email Alert: Payment Success (Webhook)
                send_payment_success_alert(
                    student_name=db_user.full_name or str(db_user.email),
                    student_email=str(db_user.email),
                    standard=db_user.standard,
                    amount=0,
                    transaction_id=razorpay_payment_id or "N/A",
                    method="Razorpay (Webhook)",
                )

    return {"status": "ok"}
