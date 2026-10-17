"""
matching_engine.py  --  the logic of the TM / job matching.  No settings here (they are in constants.py) and no printing or files
(that is main.py).

    MongoSource   reads the database
    prepare       turns one TM's raw records into past candidates
    candidate_match (score 3)  ->  build_tm (score 2)  ->  score_job (score 1)
"""

import collections
import datetime as dt
import json
import logging
import os
import re
import sys
import warnings

import numpy as np

from constants import *     # every setting and fixed table

warnings.filterwarnings("ignore")
for _k, _v in (("TQDM_DISABLE", "1"), ("HF_HUB_DISABLE_PROGRESS_BARS", "1"), ("TRANSFORMERS_VERBOSITY", "error"), ("HF_HUB_VERBOSITY", "error")):
    os.environ.setdefault(_k, _v)
for _name in ("huggingface_hub", "sentence_transformers", "transformers"):
    logging.getLogger(_name).setLevel(logging.ERROR)


# ================================================================================================ small helpers
def oid(v):
    """Any id (string, ObjectId, or the {"$oid": ...} of a JSON export) as a plain string."""
    if isinstance(v, dict):
        v = v.get("$oid")
    return None if v is None else str(v)


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, dict):
        v = v.get("$date")
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None) if v else None
    except ValueError:
        return None


def skill_key(name):
    name = name.get("name") if isinstance(name, dict) else name
    key = re.sub(r"[_\-/]+", " ", str(name or "").lower())
    key = re.sub(r"\.js\b", "js", key)
    key = re.sub(r"[^a-z0-9+#. ]", " ", key)
    key = re.sub(r"\s+", " ", key).strip(" .")
    return SYNONYMS.get(key, key)


def city_key(text):
    first = re.split(r"[,/|(]", str(text or "").lower().strip())[0].strip()
    first = CITY_OF.get(first, first)
    return None if (not first or first in NOT_CITIES) else first


def norm_email(text):
    m = re.search(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", str(text or "").lower())
    return m.group(0) if m else None


def scale(x, lo, hi):
    return float(np.clip((x - lo) / (hi - lo), 0, 1))


def stage_level(name):
    n = str(name or "").lower().strip()
    if not n or "reject" in n:
        return None
    return next((lvl for lvl, rx in STAGE_LADDER if re.search(rx, n)), None)


def user_id_in(text):
    """The 24-character id from '67d5...' or "ObjectId('67d5...')" as pasted from Compass; None when the text is a name or e-mail."""
    m = re.fullmatch(r"\s*(?:ObjectId\(\s*)?['\"]?([0-9a-fA-F]{24})['\"]?\s*\)?\s*", str(text))
    return m.group(1).lower() if m else None


# ================================================================================================ role, level, location, industry
def classify_role(title, hint="", department=None):
    """Role from the title; else from the category / department text; else from the department code; else 'Other'."""
    for text in (str(title or "").lower(), str(hint or "").lower()):
        if text:
            for name, rx in ROLE_RULES:
                if re.search(rx, text):
                    return name
    return DEPARTMENT_ROLES.get(department, "Other")


def level_from(min_years, max_years, text=""):     # for experience
    """Entry / Mid / Senior / Lead from the years asked, else from words such as 'Mid Level'."""
    if min_years or max_years:
        m = min_years or 0
        return LEVELS[0] if m <= 2 else LEVELS[1] if m <= 6 else LEVELS[2] if m <= 11 else LEVELS[3]
    t = str(text or "").lower()
    if not t:
        return None
    if re.search(r"intern|fresher|entry|junior|\bjr\b|trainee|graduate|beginner", t):
        return LEVELS[0]
    if re.search(r"lead|principal|staff|head|director|architect|manager|executive", t):
        return LEVELS[3]
    if re.search(r"senior|\bsr\b", t):
        return LEVELS[2]
    if re.search(r"mid|intermediate|associate|experienced", t):
        return LEVELS[1]
    return None


def job_record(raw, vocab_regex=None):             # puts one database job into a standard form
    """A job from the database, with its role, level, location and industry."""
    exp = raw.get("experience") or {}
    skills = {skill_key(s) for s in (raw.get("mustHaveSkills") or []) + (raw.get("coreSkills") or []) + (raw.get("mandatorySkills") or [])}
    skills.discard("")
    description = " ".join([raw.get("summary") or "", " ".join(map(str, raw.get("primaryResponsibilities") or []))])
    title = raw.get("jobTitle") or ""
    read = False
    if not skills and vocab_regex is not None:
        skills, read = read_job_skills(title + " " + description, vocab_regex), True
    cities = [c for c in (city_key(g) for g in raw.get("geographicJobLocations") or []) if c]
    industry = next((str(i).strip().lower() for i in raw.get("industry") or [] if str(i).strip()), None)
    return {"job_id": oid(raw["_id"]), "title": title, "skills": skills, "skills_read_from_text": read,
            "exp_min": exp.get("min") or 0, "exp_max": exp.get("max") or 0, "cities": set(cities),
            "remote": "REMOTE" in str(raw.get("workMode") or raw.get("jobLocation") or "").upper(),
            "degree": DEGREE_RANK.get(str((raw.get("educationalQualifications") or {}).get("degreeType") or "").lower()),
            "description": description, "created": as_date(raw.get("createdAt")),
            "role": classify_role(title, "", raw.get("jobDepartment")), "level": level_from(exp.get("min"), exp.get("max")),
            "location": cities[0] if cities else None, "industry": industry}


def resume_record(r):
    skills = {skill_key(s) for s in r.get("skills") or []}
    for level in ("basic", "medium", "advanced"):
        skills |= {skill_key(s) for s in (r.get("analysedSkills") or {}).get(level) or []}
    history = r.get("employmentHistory") or []
    for e in history:
        skills |= {skill_key(s) for s in e.get("skillsUsedInRole") or []}
    skills.discard("")
    titles = [(r.get("currentCompanyDetails") or {}).get("designation")] + [e.get("designation") for e in history[:3]]
    titles = [t.strip() for t in titles if t and t.strip()]
    exp = r.get("totalExperience") or {}
    years = (exp.get("years") or 0) + (exp.get("months") or 0) / 12 if exp else None
    if years == 0 and history:
        years = None                                    # 0 years next to a job history means "not filled in"
    edu = max((DEGREE_RANK.get(str(e.get("educationType") or "").lower(), 0) for e in r.get("educationalBackground") or []), default=0)
    work = " ".join(str(e.get("workExperienceDescription") or "") for e in history)
    return {"skills": skills, "title_text": " | ".join(dict.fromkeys(titles)), "years": years, "city": city_key(r.get("currentLocation")),
            "relocate": {c for c in (city_key(x) for x in r.get("relocationDetails") or []) if c}, "edu_rank": edu or None,
            "text": (" ".join(titles) + " " + " ".join(sorted(skills)) + " " + work)[:3000]}


def job_text(job):                                  # the text used for "meaning" similarity
    return (job["title"] + ". " + " ".join(sorted(job["skills"])) + ". " + job["description"])[:1500]


def vocab_pattern(vocab):
    words = sorted(vocab, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9+#.])(" + "|".join(re.escape(w) for w in words) + r")(?![a-z0-9+#])") if words else None


def read_job_skills(text, regex):
    if regex is None:
        return set()
    found = {m.group(1) for m in regex.finditer(text.lower())}
    return set(sorted(found, key=len, reverse=True)[:15])


# ================================================================================================ THE DATABASE
class MongoSource:
    """Reads the database (read only)."""

    def __init__(self, uri, database):                  # connect to the database
        if not uri:
            sys.exit("No database connection string. Paste it after MONGO_URI= in the .env file.")
        try:
            import pymongo
        except ImportError:
            sys.exit("To read the database install pymongo:  pip install pymongo")
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15000)
        try:
            client.admin.command("ping")
        except Exception as e:
            sys.exit(f"Could not connect to the database: {type(e).__name__}: {str(e)[:200]}\n"
                     f"Check MONGO_URI in the .env file, your network access (IP allow-list) and the user's password.")
        try:
            from bson import ObjectId
            # a 24-character id string must become a real ObjectId: the database stores ids as ObjectId, a plain string matches nothing
            self.cast = lambda x: ObjectId(x) if re.fullmatch(r"[0-9a-fA-F]{24}", str(x)) else x
        except ImportError:
            self.cast = str
        self.db = client[database]

    def _find(self, coll, query, fields=None):
        return list(self.db[coll].find(query, fields) if fields else self.db[coll].find(query))

    def owner_of(self, p, member_user):                 # works out which TM sent each candidate
        guest = oid(p.get("submittedByGuestId"))
        return member_user.get(guest) if guest else oid(p.get("addedBy"))

    # ---- which TMs
    def list_tm_ids(self):
        """Every TM who sent candidates through the platform (not the old-system 'migrated' ones), the busiest first."""
        pls = self._find("candidate_placements", {"source": {"$ne": "migrated"}}, {"addedBy": 1, "submittedByGuestId": 1})
        guests = {oid(p["submittedByGuestId"]) for p in pls if p.get("submittedByGuestId")}
        mems = self._find("workspace_memberships", {"_id": {"$in": [self.cast(g) for g in guests]}}, {"userId": 1}) if guests else []
        member_user = {oid(m["_id"]): oid(m.get("userId")) for m in mems}
        owners = collections.Counter(self.owner_of(p, member_user) for p in pls)
        return [u for u, _ in owners.most_common() if u]

    def users_by_ids(self, ids):
        docs = self._find("users", {"_id": {"$in": [self.cast(i) for i in ids]}}) if ids else []
        by_id = {oid(u["_id"]): u for u in docs}
        return [by_id.get(i, {"_id": i}) for i in ids]

    def find_user(self, ref):
        """One user from an id, an e-mail or part of a name."""
        uid = user_id_in(ref)
        if uid:
            hits = self._find("users", {"_id": self.cast(uid)})
        else:
            rx = {"$regex": re.escape(ref.strip()), "$options": "i"}
            hits = self._find("users", {"$or": [{"email": rx}, {"name": rx}]})[:50]
        ref_l = (uid or ref).lower().strip()
        exact = [u for u in hits if oid(u["_id"]) == ref_l or norm_email(u.get("email")) == ref_l or str(u.get("name") or "").lower() == ref_l]
        pool = exact if len(exact) == 1 else hits
        if not pool:
            sys.exit(f"No TM found for '{ref}'. Use the user id, the e-mail, or part of the name.")
        if len(pool) > 1:
            rows = "\n".join(f"  {str(u.get('name') or '(no name)'):28} {u.get('email') or '':38} id {oid(u['_id'])}" for u in pool[:20])
            sys.exit(f"More than one TM matches '{ref}'. Use the user id or the e-mail:\n{rows}")
        return pool[0]

    # ---- which jobs
    def latest_jobs(self, status, limit):
        """The `limit` most recently created jobs with this status."""
        cursor = self.db["jobdescriptions"].find({"status": status}).sort([("createdAt", -1), ("_id", -1)]).limit(limit).allow_disk_use(True)
        return list(cursor)

    # ---- one TM's data
    def tm_raw(self, uid):                              # fetch everything about the TM
        mems = self._find("workspace_memberships", {"userId": self.cast(uid)})
        mids = [oid(m["_id"]) for m in mems]
        assigned = {oid(j) for m in mems for j in (m.get("accessScope") or {}).get("atsJobs") or []}
        query = {"$or": [{"addedBy": self.cast(uid)}] + ([{"submittedByGuestId": {"$in": [self.cast(i) for i in mids]}}] if mids else []),
                 "source": {"$ne": "migrated"}}
        member_user = {m: uid for m in mids}
        pls = [p for p in self._find("candidate_placements", query) if self.owner_of(p, member_user) == uid]
        ids = lambda key: list({oid(p.get(key)) for p in pls if p.get(key)})
        hist_docs = self._find("placement_stage_histories", {"placementId": {"$in": [self.cast(i) for i in ids("_id")]}}) if pls else []
        history = collections.defaultdict(list)
        for h in hist_docs:
            history[oid(h["placementId"])].append(h)
        stage_ids = set(ids("stageId")) | {oid(h.get(k)) for h in hist_docs for k in ("toStageId", "fromStageId") if h.get(k)}
        job_ids = set(ids("jobId")) | assigned
        job_docs = {oid(j["_id"]): j for j in self._find("jobdescriptions", {"_id": {"$in": [self.cast(i) for i in job_ids]}})}
        worked = set(ids("jobId"))
        return {"placements": pls, "assigned": assigned, "history": history,
                "resumes": {oid(r["_id"]): r for r in self._find("resumes", {"_id": {"$in": [self.cast(i) for i in ids("resumeId")]}})},
                "jobs": {j: d for j, d in job_docs.items() if j in worked}, "assigned_jobs": {j: d for j, d in job_docs.items() if j in assigned},
                "stages": {oid(s["_id"]): s for s in self._find("pipeline_stages", {"_id": {"$in": [self.cast(i) for i in stage_ids]}})}}

    def skill_vocab(self):
        """Skill names that appear in at least 5 jobs (from coreSkills and mustHaveSkills); used to read skills out of job text when a job lists none."""
        cache = os.path.join(OUTPUT_DIR, "skill_vocab.json")
        if os.path.exists(cache):
            return set(json.load(open(cache, encoding="utf-8")))
        names = {"$map": {"input": {"$concatArrays": [{"$ifNull": ["$coreSkills", []]}, {"$ifNull": ["$mustHaveSkills", []]}]},
                          "as": "x", "in": {"$ifNull": ["$$x.name", "$$x"]}}}
        pipeline = [{"$project": {"s": {"$setUnion": [names, []]}}}, {"$unwind": "$s"}, {"$group": {"_id": "$s", "n": {"$sum": 1}}}]
        count = collections.Counter()
        for row in self.db["jobdescriptions"].aggregate(pipeline):
            count[skill_key(row["_id"])] += row["n"]
        vocab = {s for s, n in count.items() if n >= 5 and len(s) >= 3}
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        json.dump(sorted(vocab), open(cache, "w", encoding="utf-8"))
        return vocab


# ================================================================================================ THE TM'S PAST CANDIDATES
def prepare(raw, vocab_regex):     # turns the TM's raw records into candidates with stage, early rejection, test result and review
    """Raw records -> the TM's past jobs and candidates, each candidate with the stage reached, early rejection, test result and team review."""
    stages = raw["stages"]
    jobs = {jid: job_record(doc, vocab_regex) for jid, doc in raw["jobs"].items()}
    assigned = {jid: job_record(doc, vocab_regex) for jid, doc in raw.get("assigned_jobs", {}).items()}
    name_of = lambda sid_: str((stages.get(oid(sid_)) or {}).get("name") or "")
    cands = []
    for p in raw["placements"]:
        pid, rid, jid = oid(p["_id"]), oid(p.get("resumeId")), oid(p.get("jobId"))
        if rid not in raw["resumes"] or jid not in jobs:
            continue
        hist = raw["history"].get(pid, [])
        names = [name_of(p.get("stageId"))] + [name_of(h.get("toStageId")) for h in hist] + [name_of(h.get("fromStageId")) for h in hist]
        levels = [stage_level(n) for n in names]
        level = max((l for l in levels if l), default=1)
        current = stages.get(oid(p.get("stageId"))) or {}
        rejected = (current.get("terminalOutcome") == "rejected" and bool(current.get("isTerminal"))) or "reject" in name_of(p.get("stageId")).lower()
        if current.get("terminalOutcome") == "hired" and current.get("isTerminal"):
            level = TOP_LEVEL
        reasons = {str((p.get("capturedDetails") or {}).get("rejectionReason") or "").lower()}
        reasons |= {str((h.get("metadata") or {}).get("rejectionReason") or "").lower() for h in hist}
        reasons |= {"existing-micro1-user" for h in hist if "existing-micro1-user" in str(h.get("note") or "").lower()}
        early = bool(reasons & EARLY_REASONS) or (rejected and level <= SHORTLIST_LEVEL)
        took_test = 4 in levels or "failed_ai_interview" in reasons
        if not took_test:
            test = None
        elif any("certified" in n.lower() for n in names) or level >= 5:
            test = True
        elif "failed_ai_interview" in reasons or (rejected and level == 4):
            test = False
        else:
            test = None                                 # took it, no verdict yet
        review = str(p.get("reviewStatus") or "").lower()
        cands.append({"pid": pid, "resume_id": rid, "job_id": jid, "job": jobs[jid], "created": as_date(p.get("createdAt")),
                      "rec": resume_record(raw["resumes"][rid]), "level": level, "early": early, "test": test,
                      "shortlisted": level >= SHORTLIST_LEVEL and not early,
                      "approved": (1.0 if review == "approved" else 0.0) if review in ("approved", "rejected", "needs_more_info") else None})
    return {"cands": cands, "jobs": jobs, "assigned": assigned}


def pool_of(cands):     # one entry per resume, so a resume sent to two jobs is not counted twice
    """The TM's pool of past candidates: one entry per resume."""
    seen, out = set(), []
    for c in cands:
        if c["resume_id"] not in seen:
            seen.add(c["resume_id"])
            out.append(c)
    return out


class Embedder:     # the free local model for title and meaning similarity
    """Sentence meaning with a free local model; every text is encoded once (the cache is kept across TMs)."""

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            sys.exit("This script needs sentence-transformers:  pip install sentence-transformers")
        self.cache = {}

    def warm(self, texts):
        new = sorted({t for t in texts if t and t not in self.cache})
        if new:
            for t, v in zip(new, self.model.encode(new, batch_size=64, normalize_embeddings=True, show_progress_bar=False)):
                self.cache[t] = v

    def vec(self, text):
        self.warm([text])
        return self.cache[text]


# ================================================================================================ SCORE 3: CANDIDATE MATCH
def candidate_match(rec, job, E):
    """One resume against the job it was sent for, 0-100 (skills 40, experience 25, title 15, location 10, education 5, meaning 5)."""
    parts = {}
    if job["skills"]:
        parts["skills"] = 100 * len(rec["skills"] & job["skills"]) / len(job["skills"])
    if rec["years"] is not None and (job["exp_min"] or job["exp_max"]):
        lo, hi = job["exp_min"], (job["exp_max"] if job["exp_max"] > job["exp_min"] else None)
        parts["experience"] = max(0.0, 100 - 25 * (lo - rec["years"])) if rec["years"] < lo else \
            (max(0.0, 100 - 10 * (rec["years"] - hi)) if hi is not None and rec["years"] > hi else 100.0)
    if rec["title_text"] and job["title"]:
        parts["title"] = 100 * scale(float(E.vec(rec["title_text"]) @ E.vec(job["title"])), *TITLE_ANCHORS)
    if job["cities"] and not job["remote"] and rec["city"]:
        parts["location"] = 100.0 if rec["city"] in job["cities"] else 70.0 if rec["relocate"] & job["cities"] else 30.0
    if job["degree"] and rec["edu_rank"]:
        parts["education"] = 100.0 if rec["edu_rank"] >= job["degree"] else 60.0 if rec["edu_rank"] == job["degree"] - 1 else 20.0
    if rec["text"]:
        parts["meaning"] = max(0.0, float(E.vec(rec["text"]) @ E.vec(job_text(job)))) * 100
    total = sum(MATCH_WEIGHTS[k] for k in parts)
    return sum(MATCH_WEIGHTS[k] * v for k, v in parts.items()) / total if total else None


# ================================================================================================ SCORE 2: THE TM SCORE PER GROUP
def build_tm(prep, E):
    """The TM's groups. A group = one role, one level, one location or one industry. Each gets a TM score from the TM's own candidates."""
    cands = prep["cands"]
    if not cands:                                       # nothing to learn from: no groups, so no job can be scored
        return {"groups": {d: {} for d in ("role", "level", "location", "industry")}, "typical": {}, "good_skills": collections.Counter(),
                "n_pool": 0, "n_jobs": 0, "n_cands": 0}
    E.warm([c["rec"]["text"] for c in cands] + [c["rec"]["title_text"] for c in cands] + [j["title"] for j in prep["jobs"].values()]
           + [job_text(j) for j in prep["jobs"].values()])
    for c in cands:
        c["match"] = candidate_match(c["rec"], c["job"], E)

    by_job = collections.defaultdict(list)              # the candidates grouped by job
    for c in cands:
        by_job[c["job_id"]].append(c)
    days = {}
    for jid, cs in by_job.items():                      # speed: days from the job being created to the TM's first submission
        first, created = min((c["created"] for c in cs if c["created"]), default=None), cs[0]["job"]["created"]
        if first and created and 0 <= (first - created).total_seconds() / 86400 <= SPEED_WINDOW_DAYS:
            days[jid] = (first - created).total_seconds() / 86400
    median_per_job = max(float(np.median([len(cs) for cs in by_job.values()])), 1.0)
    typical_days = max(float(np.median(list(days.values()))) if days else 1.0, 1.0)
    worked = set(by_job)

    def mean_or_none(vals):                             # plain average of real data; None when there is nothing to average
        return float(np.mean(vals)) if vals else None

    def stats(rows, dim, value):
        jids = {c["job_id"] for c in rows}
        f = {"progress": mean_or_none([c["level"] / TOP_LEVEL for c in rows]),
             "test": mean_or_none([float(c["test"]) for c in rows if c["test"] is not None]),
             "match": mean_or_none([c["match"] / 100 for c in rows if c["match"] is not None]),
             "approval": mean_or_none([c["approved"] for c in rows if c["approved"] is not None]),
             "early": mean_or_none([1.0 - c["early"] for c in rows]),
             "volume": min(len(rows) / len(jids) / median_per_job, 1.0)}
        given = {j for j, rec in prep["assigned"].items() if rec[dim] == value}
        f["coverage"] = len(given & worked) / len(given) if given else None
        d = [days[j] for j in jids if j in days]
        f["speed"] = float(np.clip(1 - np.median(d) / (2 * typical_days), 0, 1)) if d else None
        have = {k: v for k, v in f.items() if v is not None}
        n = len(rows)
        return {"n": n, "jobs": len(jids), "score": sum(TM_WEIGHTS[k] * v for k, v in have.items()) / sum(TM_WEIGHTS[k] for k in have),
                "factors": have, "confidence": "Low" if n < 5 else "Medium" if n <= 15 else "High",
                "shortlisted": sum(c["shortlisted"] for c in rows) / n,
                "match100": float(np.mean([c["match"] for c in rows if c["match"] is not None])) if any(c["match"] is not None for c in rows) else None}

    groups = {}
    for dim in ("role", "level", "location", "industry"):
        buckets = collections.defaultdict(list)
        for c in cands:
            if c["job"][dim] is not None:
                buckets[c["job"][dim]].append(c)
        groups[dim] = {value: stats(rows, dim, value) for value, rows in buckets.items()}
    typical = {dim: float(np.median([g["score"] for g in gs.values() if g["n"] >= MIN_GROUP_CANDIDATES]))
               for dim, gs in groups.items() if any(g["n"] >= MIN_GROUP_CANDIDATES for g in gs.values())}

    good = collections.Counter()                        # skills of the jobs where the TM's candidates did well
    for c in cands:
        if ((c["match"] or 0) >= GOOD_MATCH and not c["early"]) or c["level"] >= CLIENT_LEVEL:
            good.update(c["job"]["skills"])
    return {"groups": groups, "typical": typical, "good_skills": good, "n_pool": len(pool_of(cands)), "n_jobs": len(by_job),
            "n_cands": len(cands)}


# ================================================================================================ SCORE 1: THE JOB FIT
def score_job(job, tm):
    """The five parts of the job fit, and the reasons. Returns (fit 0-1 or None, confidence, parts, reasons)."""
    parts, lines = {}, []
    nice = {"role": "Role", "level": "Level", "location": "Location", "industry": "Industry"}
    for dim in ("role", "level", "location", "industry"):
        value, groups = job[dim], tm["groups"][dim]
        if value is None:
            if dim in tm["typical"]:
                parts[dim] = tm["typical"][dim]
                lines.append(("~", f"{nice[dim]}: the job does not say, so the TM's typical {dim} score is used"))
            continue
        if not groups:
            continue                                    # the TM's history says nothing about this property at all
        g = groups.get(value)
        if g is not None and g["n"] >= MIN_GROUP_CANDIDATES:
            parts[dim] = g["score"]
            typ = tm["typical"].get(dim, g["score"])
            mark = "+" if g["score"] >= typ * 1.05 else "!" if g["score"] <= typ * 0.9 else "~"
            text = f"{nice[dim]}: sent {g['n']} candidates for {value} jobs ({g['jobs']} jobs); {100 * g['shortlisted']:.0f}% shortlisted"
            if g["match100"] is not None:
                text += f"; matched their job descriptions {g['match100']:.0f}/100"
            lines.append((mark, text + f" (confidence {g['confidence']})"))
        else:
            parts[dim] = UNSEEN_SCORE
            lines.append(("!", f"{nice[dim]}: has not worked on {value} jobs before (trial score {UNSEEN_SCORE:.2f})" if g is None else
                          f"{nice[dim]}: only {g['n']} candidates for {value} jobs ({MIN_GROUP_CANDIDATES} needed), so it counts as a trial"))
    if job["skills"] and tm["good_skills"] and (not job.get("skills_read_from_text") or len(job["skills"]) >= 3):
        have = sorted(s for s in job["skills"] if s in tm["good_skills"])
        parts["skills"] = len(have) / len(job["skills"])
        lines.append(("+" if parts["skills"] >= 0.5 else "!", f"Skills: {len(have)} of {len(job['skills'])} required skills appeared in jobs where the TM's candidates did well"
                      + (f" ({', '.join(have[:5])})" if have else "")))
    if not parts:
        return None, "Low", parts, lines
    fit = sum(JOB_FIT_WEIGHTS[k] * v for k, v in parts.items()) / sum(JOB_FIT_WEIGHTS[k] for k in parts)
    role_g = tm["groups"]["role"].get(job["role"])
    conf = role_g["confidence"] if role_g is not None and role_g["n"] >= MIN_GROUP_CANDIDATES else "Low"
    return fit, conf, parts, lines
