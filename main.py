"""
main.py  --  for each job, compare it with ALL the talent managers (TMs).

    1. connect to the database (the connection string is in the .env file)
    2. pull the ids from the database: every TM id, and the next BATCH_JOBS job ids that are not done yet
    3. build each TM's scores once
    4. for each job: score every TM for it (percentage and reasons), and save ALL the TMs of that
       job in Output/<job_title>_<job_id>.json.  Nothing is shown on the screen.
    5. next run: the next BATCH_JOBS jobs

RUN   python main.py        (needs  pip install numpy sentence-transformers pymongo)
"""

import datetime as dt
import json
import os
import re
import sys

import constants as C
from matching_engine import (Embedder, MongoSource, build_tm, job_record, norm_email, oid, prepare, score_job, vocab_pattern)


# ---- which ids are already done (so every run takes new ones)
def load_progress():
    try:
        data = json.load(open(C.PROGRESS_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"tms": set(data.get("tms", [])), "jobs": set(data.get("jobs", []))}


def mark_done(kind, ids):
    progress = load_progress()
    progress[kind] |= set(ids)
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    json.dump({k: sorted(v) for k, v in progress.items()}, open(C.PROGRESS_FILE, "w", encoding="utf-8"))


def next_ids(all_ids, done, size, what):
    """The first `size` ids (in database order) that are not done yet."""
    ids = [i for i in all_ids if i not in done]
    if not ids:
        sys.exit(f"Every {what} is already done ({len(done)}). Delete {C.PROGRESS_FILE} to start again from the first one.")
    return ids[:size] if size else ids


# ---- scoring
def rank_tms(job, tms):
    """Every TM of the batch scored for one job, best first. tms = list of (user, profile)."""
    scored = []
    for user, profile in tms:
        fit, conf, parts, lines = score_job(job, profile)
        good, watch, notes = ([t for m, t in lines if m == mark] for mark in ("+", "!", "~"))
        if fit is None:
            watch = ["Could not be scored: this TM has no past candidates to learn from"]
        scored.append((fit, {"tm_id": oid(user["_id"]), "tm_name": user.get("name"), "tm_email": norm_email(user.get("email")),
                             "past_candidates": profile["n_cands"], "match_percent": None if fit is None else int(round(100 * fit)),
                             "confidence": conf, "good": good, "watch": watch, "notes": notes,
                             "parts": {k: round(v, 3) for k, v in parts.items()}}))
    scored.sort(key=lambda s: -(s[0] if s[0] is not None else -1))
    return [{"rank": rank, **entry} for rank, (_, entry) in enumerate(scored, 1)]


# ---- output
def save_job(job, ranked):
    """One JSON file per job with all the TMs, best first."""
    name = re.sub(r"[^\w\-]+", "_", str(job["title"] or "no_title")).strip("_")[:40]
    path = os.path.join(C.OUTPUT_DIR, f"{name}_{job['job_id']}.json")
    data = {"job": {"id": job["job_id"], "title": job["title"], "role": job["role"], "level": job["level"], "location": job["location"],
                    "industry": job["industry"], "skills": sorted(job["skills"])},
            "created": dt.datetime.now().isoformat(timespec="seconds"), "tms_compared": len(ranked), "tms": ranked}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def main():
    source = MongoSource(C.MONGO_URI, C.DATABASE)
    vocab_regex = vocab_pattern(source.skill_vocab())
    job_ids = next_ids(source.list_job_ids(), load_progress()["jobs"], C.BATCH_JOBS, "job")
    users = source.users_by_ids(source.list_tm_ids())    # ALL the TM ids
    jobs = [job_record(d, vocab_regex) for d in source.jobs_by_ids(job_ids)]

    E = Embedder()
    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    tms = []
    for user in users:                                   # each TM's scores are built once and used for every job
        tms.append((user, build_tm(prepare(source.tm_raw(oid(user["_id"])), vocab_regex), E)))

    for job in jobs:
        ranked = rank_tms(job, tms)
        save_job(job, ranked)
        mark_done("jobs", [job["job_id"]])               # only after its file is saved


if __name__ == "__main__":
    main()
