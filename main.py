"""
main.py  --  for each talent manager (TM), score every active job and write one CSV.

    1. connect to the database (the connection string is in the .env file)
    2. pull the job list from the database: the latest JOBS_LIMIT jobs whose status is JOB_STATUS
    3. pull the TM list: TM_IDS, or TM_SAMPLE random TMs who sent candidates through the platform
    4. for each TM: build the TM's scores once, then score every job against them
    5. write Output/tm_job_scores_<date_time>.csv  (one row per TM and job, best job first within each TM)

RUN   python main.py        (needs  pip install numpy sentence-transformers pymongo)
"""

import csv
import datetime as dt
import os
import random
import sys
import time

import constants as C
from matching_engine import (Embedder, MongoSource, build_tm, job_record, norm_email, oid, prepare, score_job, vocab_pattern)


def pull_jobs(source, vocab_regex):
    docs = source.latest_jobs(C.JOB_STATUS, C.JOBS_LIMIT)
    if not docs:
        sys.exit(f"No jobs with status '{C.JOB_STATUS}' found in jobdescriptions.")
    return [job_record(d, vocab_regex) for d in docs]


def pull_tms(source):
    if C.TM_IDS:                                        # TMs named in constants.py
        return [source.find_user(ref) for ref in C.TM_IDS]
    ids = source.list_tm_ids()
    if C.TM_SAMPLE and len(ids) > C.TM_SAMPLE:
        ids = random.Random(C.RANDOM_SEED).sample(ids, C.TM_SAMPLE)
    return source.users_by_ids(ids)


def reasons(lines):
    """The reason lines as three CSV cells: what supports the fit (+), the warnings (!), and the neutral notes (~)."""
    cell = lambda mark: " | ".join(t for m, t in lines if m == mark)
    return cell("+"), cell("!"), cell("~")


def rows_for_tm(user, profile, jobs):
    """Every job scored for one TM, best first, with its rank."""
    scored = []
    for job in jobs:
        fit, conf, parts, lines = score_job(job, profile)
        scored.append((fit, conf, parts, lines, job))
    scored.sort(key=lambda s: -(s[0] if s[0] is not None else -1))
    rows = []
    for rank, (fit, conf, parts, lines, job) in enumerate(scored, 1):
        why, watch, notes = reasons(lines)
        rows.append({"tm_id": oid(user["_id"]), "tm_name": user.get("name") or "", "tm_email": norm_email(user.get("email")) or "",
                     "tm_candidates": profile["n_cands"], "job_id": job["job_id"], "job_title": job["title"], "role": job["role"],
                     "level": job["level"] or "", "location": job["location"] or "", "industry": job["industry"] or "",
                     "rank_for_tm": rank, "in_top_n": "Yes" if fit is not None and rank <= C.TOP_N else "No",
                     "match_percent": "" if fit is None else int(round(100 * fit)), "confidence": conf,
                     **{f"part_{k}": "" if k not in parts else round(parts[k], 3) for k in ("role", "level", "skills", "location", "industry")},
                     "why": why, "watch_out": watch, "notes": notes})
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    started = time.time()
    source = MongoSource(C.MONGO_URI, C.DATABASE)
    vocab_regex = vocab_pattern(source.skill_vocab())
    jobs = pull_jobs(source, vocab_regex)
    tms = pull_tms(source)
    print(f"{len(tms)} TMs x {len(jobs)} {C.JOB_STATUS} jobs")
    for u in tms:
        print(f"  {u.get('name') or '(no name)':30} {oid(u['_id'])}")
    E = Embedder()

    os.makedirs(C.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(C.OUTPUT_DIR, f"tm_job_scores_{dt.datetime.now():%Y%m%d_%H%M%S}.csv")
    total = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=C.CSV_COLUMNS)
        writer.writeheader()
        for i, user in enumerate(tms, 1):
            t0 = time.time()
            profile = build_tm(prepare(source.tm_raw(oid(user["_id"])), vocab_regex), E)
            rows = rows_for_tm(user, profile, jobs)
            writer.writerows(rows)
            f.flush()                                   # a crash later does not lose the TMs already done
            total += len(rows)
            print(f"[{i}/{len(tms)}] {user.get('name') or oid(user['_id'])}: {profile['n_cands']} past candidates, {len(rows)} jobs scored ({time.time() - t0:.0f}s)")
    print(f"\nDone: {total} rows in {(time.time() - started) / 60:.1f} min\n{path}")


if __name__ == "__main__":
    main()
