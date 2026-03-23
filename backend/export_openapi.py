import json
from app.main import app
from fastapi.openapi.utils import get_openapi

openapi_schema = get_openapi(
    title=app.title,
    version=app.version,
    openapi_version=app.openapi_version,
    description=app.description,
    routes=app.routes,
)

with open("../frontend/openapi.json", "w") as f:
    json.dump(openapi_schema, f, indent=2)

print("Exported openapi.json to ../frontend/openapi.json")
