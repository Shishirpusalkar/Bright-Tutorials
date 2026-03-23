import uuid
from datetime import datetime, timezone

# In-memory store for AI parsing jobs
# In production, this would be Redis or a Database
ai_parsing_jobs = {}


def create_job():
    job_id = str(uuid.uuid4())
    ai_parsing_jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Initializing...",
        "created_at": datetime.now(timezone.utc),
        "question_cache": [],
    }
    return job_id


def update_job(job_id, progress=None, message=None, status=None):
    if job_id in ai_parsing_jobs:
        if progress is not None:
            ai_parsing_jobs[job_id]["progress"] = progress
        if message is not None:
            ai_parsing_jobs[job_id]["message"] = message
        if status is not None:
            ai_parsing_jobs[job_id]["status"] = status


def get_job(job_id):
    return ai_parsing_jobs.get(job_id)


def set_job_question_cache(job_id, questions):
    if job_id in ai_parsing_jobs:
        ai_parsing_jobs[job_id]["question_cache"] = questions


def get_job_question_cache(job_id):
    job = ai_parsing_jobs.get(job_id)
    if not job:
        return []
    return job.get("question_cache", [])


def cleanup_old_jobs():
    # Simple cleanup logic to avoid memory bloat
    now = datetime.now(timezone.utc)
    to_delete = []
    for jid, job in ai_parsing_jobs.items():
        delta = (now - job["created_at"]).total_seconds()
        if delta > 3600:  # 1 hour
            to_delete.append(jid)
    for jid in to_delete:
        del ai_parsing_jobs[jid]
