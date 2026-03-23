from sqlmodel import Session, create_engine, select
from app.models import User, Test, Question, Attempt
from app.core.config import settings
import pandas as pd

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def dump_db():
    tables = {"Users": User, "Tests": Test, "Questions": Question, "Attempts": Attempt}

    with Session(engine) as session:
        for name, model in tables.items():
            print(f"\n=== {name} ===")
            statement = select(model)
            results = session.exec(statement).all()
            if results:
                # Use pandas to print a nice table
                df = pd.DataFrame([r.model_dump() for r in results])
                print(df.to_string(index=False))
            else:
                print("Empty table.")


if __name__ == "__main__":
    dump_db()
