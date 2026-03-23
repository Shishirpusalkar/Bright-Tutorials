from io import BytesIO

import pandas as pd
from sqlmodel import Session, select

from app.models import User


def export_users_to_excel(session: Session) -> BytesIO:
    """
    Exports the users table to an Excel file (in-memory).
    """
    statement = select(User)
    users = session.exec(statement).all()

    # Convert SQLModel objects to a list of dicts for pandas
    data = []
    for user in users:
        data.append(
            {
                "ID": str(user.id),
                "Email": user.email,
                "Full Name": user.full_name or "N/A",
                "Role": user.role,
                "Active": user.is_active,
                "Premium": user.is_premium,
                "Created At": user.created_at.replace(tzinfo=None)
                if user.created_at
                else "N/A",
            }
        )

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Users")

    output.seek(0)
    return output


def export_users_to_csv(session: Session) -> BytesIO:
    """
    Exports the users table to a CSV file (in-memory).
    """
    statement = select(User)
    users = session.exec(statement).all()

    data = []
    for user in users:
        data.append(
            {
                "ID": str(user.id),
                "Email": user.email,
                "Full Name": user.full_name or "N/A",
                "Role": user.role,
                "Grade": user.grade or "N/A",
                "Standard": user.standard or "N/A",
                "Paid": user.is_paid,
                "Payment ID": user.payment_id or "N/A",
                "Payment Status": user.payment_status or "N/A",
                "Fee Override": user.fee_override,
                "Fee Exempt": user.is_fee_exempt,
                "Premium Expiry": user.premium_expiry.isoformat()
                if user.premium_expiry
                else "N/A",
                "Created At": user.created_at.isoformat() if user.created_at else "N/A",
                "Last Active": user.last_active_at.isoformat()
                if user.last_active_at
                else "N/A",
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output
