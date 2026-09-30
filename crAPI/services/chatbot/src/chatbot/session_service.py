import os
import uuid
from .config import Config
from quart import after_this_request, request

from .extensions import db

SESSION_COOKIE_NAME = "chat_session_id"


async def get_or_create_session_id():
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id or not session_id.strip():
        session_id = str(uuid.uuid4())

        @after_this_request
        def after_index(response):
            forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
            is_secure = request.scheme == "https" or forwarded_proto == "https"
            response.set_cookie(
                SESSION_COOKIE_NAME,
                session_id,
                httponly=True,
                secure=is_secure,
                samesite="Lax",
            )
            return response

    return session_id


async def store_api_key(session_id, api_key):
    await db.sessions.update_one(
        {"session_id": session_id}, {"$set": {"openai_api_key": api_key}}, upsert=True
    )


async def get_api_key(session_id):
    if os.environ.get("CHATBOT_OPENAI_API_KEY"):
        return os.environ.get("CHATBOT_OPENAI_API_KEY")
    doc = await db.sessions.find_one({"session_id": session_id})
    if not doc:
        return None
    if "openai_api_key" not in doc:
        return None
    return doc["openai_api_key"]


async def delete_api_key(session_id):
    await db.sessions.update_one(
        {"session_id": session_id}, {"$unset": {"openai_api_key": ""}}
    )


async def store_model_name(session_id, model_name):
    await db.sessions.update_one(
        {"session_id": session_id}, {"$set": {"model_name": model_name}}, upsert=True
    )


async def get_model_name(session_id):
    doc = await db.sessions.find_one({"session_id": session_id})
    if not doc:
        return Config.DEFAULT_MODEL_NAME
    if "model_name" not in doc:
        return Config.DEFAULT_MODEL_NAME
    return doc["model_name"]


async def get_user_jwt() -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None

    scheme, separator, token = auth.partition(" ")
    if separator == "" or scheme.lower() != "bearer":
        return None

    token = token.strip()
    if not token:
        return None
    return token
