"""
matching_engine.py  --  the main steps of the TM / job matching.  The settings are in constants.py, the small helper functions
are in helper.py, and main.py runs the steps in order.

    MongoSource               reads the data of the database (it never changes anything)
    prepare_candidates        turns the data of one TM into a list of the TM's past candidates
    candidate_match_score     score 3: how well one candidate's resume matched the job it was sent for (0 to 100)
    build_tm_profile          score 2: how well the TM did in each group (one role, level, city or industry)
    score_job_for_tm          score 1: how well a new job fits the TM (the percentage), with the reasons
"""

import collections
import json
import logging
import os
import sys
import warnings

import numpy as np

import constants
import helper

# The text-model library prints progress bars and notices by default.  These lines keep the screen quiet.
warnings.filterwarnings("ignore")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
for library_name in ("huggingface_hub", "sentence_transformers", "transformers"):
    logging.getLogger(library_name).setLevel(logging.ERROR)


# ================================================================================================ THE DATABASE
class MongoSource:
    """Reads the MongoDB database.  It only reads, it never changes anything."""

    def __init__(self, connection_string, database_name):
        """Connects to the database and checks that the connection works."""
        if not connection_string:
            sys.exit("No database connection string. Paste it after MONGO_URI= in the .env file.")
        try:
            import pymongo
        except ImportError:
            sys.exit("To read the database install pymongo:  pip install pymongo")
        client = pymongo.MongoClient(connection_string, serverSelectionTimeoutMS=15000)
        try:
            client.admin.command("ping")
        except Exception as error:
            sys.exit(f"Could not connect to the database: {type(error).__name__}: {str(error)[:200]}\n"
                     f"Check MONGO_URI in the .env file, your network access (IP allow-list) and the user's password.")
        self.database = client[database_name]

    def get_users(self, user_ids): # read the tms # give list of user id text
        """The users of these ids, in the same order.  An id that is not in the database gives a record with only the id."""
        found = helper.find_by_ids(self.database, "users", user_ids)
        user_by_id = {}
        for user in found:
            user_by_id[helper.id_as_text(user["_id"])] = user
        users = []
        for user_id in user_ids:
            users.append(user_by_id.get(user_id, {"_id": user_id}))
        return users

    def get_jobs(self, job_ids): #reads the jobs
        """The jobs of these ids, in the same order.  An id that is not in the database is skipped."""
        found = helper.find_by_ids(self.database, "jobdescriptions", job_ids)
        job_by_id = {}
        for job in found:
            job_by_id[helper.id_as_text(job["_id"])] = job
        jobs = []
        for job_id in job_ids:
            if job_id in job_by_id:
                jobs.append(job_by_id[job_id])
        return jobs

    def get_tm_data(self, tm_id):# everything about one TM
        """Everything the database knows about one TM: the candidates sent (placements), their resumes and stages, and the jobs."""
        db = self.database

        # The TM's workspace memberships.  A candidate can be sent through a membership instead of the TM's own id.
        memberships = helper.find_all(db, "workspace_memberships", {"userId": helper.to_object_id(tm_id)})
        membership_ids = [helper.id_as_text(membership["_id"]) for membership in memberships]
        member_to_user = {}
        for membership_id in membership_ids:
            member_to_user[membership_id] = tm_id

        # The jobs assigned to this TM.
        assigned_job_ids = set()
        for membership in memberships:
            access = membership.get("accessScope") or {}
            for job_id in access.get("atsJobs") or []:
                assigned_job_ids.add(helper.id_as_text(job_id))

        # The placements: one candidate sent for one job.  The ones with source "migrated" (the old system) are left out.
        sent_by = [{"addedBy": helper.to_object_id(tm_id)}]
        if membership_ids:
            sent_by.append({"submittedByGuestId": {"$in": [helper.to_object_id(i) for i in membership_ids]}})
        query = {"$or": sent_by, "source": {"$ne": "migrated"}} # or -either condition for addedby and submittedby
        # ne- not equal 
        placements = []
        for placement in helper.find_all(db, "candidate_placements", query): # the list of tm placements
            if helper.find_owner(placement, member_to_user) == tm_id:
                placements.append(placement)

        # The stage history of these placements, and the names of all the stages used.
        history_rows = helper.find_by_ids(db, "placement_stage_histories", helper.unique_values(placements, "_id"), "placementId")
        history_by_placement = collections.defaultdict(list)
        for row in history_rows:
            history_by_placement[helper.id_as_text(row["placementId"])].append(row)
        #collect every stage id used, current stage of each placement     
        stage_ids = set(helper.unique_values(placements, "stageId"))
        for row in history_rows:
            for field_name in ("toStageId", "fromStageId"):
                if row.get(field_name):
                    stage_ids.add(helper.id_as_text(row[field_name]))
        stages = {}
        for stage in helper.find_by_ids(db, "pipeline_stages", list(stage_ids)):
            stages[helper.id_as_text(stage["_id"])] = stage

        # The resumes of the candidates.
        resumes = {}
        for resume in helper.find_by_ids(db, "resumes", helper.unique_values(placements, "resumeId")):
            resumes[helper.id_as_text(resume["_id"])] = resume

        # The jobs the TM sent candidates for, and the jobs assigned to the TM.
        worked_job_ids = set(helper.unique_values(placements, "jobId"))
        all_job_ids = list(worked_job_ids | assigned_job_ids)
        worked_jobs = {}
        assigned_jobs = {}
        for job in helper.find_by_ids(db, "jobdescriptions", all_job_ids):
            job_id = helper.id_as_text(job["_id"])
            if job_id in worked_job_ids:
                worked_jobs[job_id] = job
            if job_id in assigned_job_ids:
                assigned_jobs[job_id] = job

        return {"placements": placements, "history_by_placement": history_by_placement, "stages": stages, "resumes": resumes,
                "worked_jobs": worked_jobs, "assigned_jobs": assigned_jobs}

    def get_skill_list(self):
        """The skill names that appear in at least 5 jobs.  They are used to find skills in the text of a job that lists none.
        The list is saved in a file after the first time, so the next runs do not count again."""
        cache_file = os.path.join(constants.OUTPUT_DIR, "skill_list.json")
        if os.path.exists(cache_file):
            return set(json.load(open(cache_file, encoding="utf-8")))

        # Ask the database to count how many jobs list each skill (coreSkills and mustHaveSkills).
        both_lists = {"$concatArrays": [{"$ifNull": ["$coreSkills", []]}, {"$ifNull": ["$mustHaveSkills", []]}]}
        skill_names = {"$map": {"input": both_lists, "as": "skill", "in": {"$ifNull": ["$$skill.name", "$$skill"]}}}
        steps = [{"$project": {"skills": {"$setUnion": [skill_names, []]}}}, #union-keep each job’s skills without repeats 
                 {"$unwind": "$skills"},# give one row per skill
                 {"$group": {"_id": "$skills", "jobs": {"$sum": 1}}}]
        job_count = collections.Counter()
        for row in self.database["jobdescriptions"].aggregate(steps):
            job_count[helper.clean_skill(row["_id"])] += row["jobs"]

        skill_list = set()
        for skill, count in job_count.items():
            if count >= 5 and len(skill) >= 3:
                skill_list.add(skill)
        os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
        json.dump(sorted(skill_list), open(cache_file, "w", encoding="utf-8"))
        return skill_list


# ================================================================================================ THE TM'S PAST CANDIDATES
def prepare_candidates(tm_data, skill_pattern): # turn raw data(get tm data) into clean list of tm past candidates
    """Turns the data of one TM into the list of the TM's past candidates.
    For each candidate it works out: the stage reached, if rejected early, the test result and the team review."""
    stages = tm_data["stages"]
    worked_jobs = {}
    for job_id, raw_job in tm_data["worked_jobs"].items():
        worked_jobs[job_id] = helper.make_job(raw_job, skill_pattern)
    assigned_jobs = {}
    for job_id, raw_job in tm_data["assigned_jobs"].items():
        assigned_jobs[job_id] = helper.make_job(raw_job, skill_pattern)

    candidates = []
    for placement in tm_data["placements"]:
        placement_id = helper.id_as_text(placement["_id"])
        resume_id = helper.id_as_text(placement.get("resumeId"))
        job_id = helper.id_as_text(placement.get("jobId"))
        if resume_id not in tm_data["resumes"] or job_id not in worked_jobs:
            continue                    # without the resume or the job there is nothing to compare

        # All the stage names this candidate has been in: the current one, and the ones before and after in the history.
        history = tm_data["history_by_placement"].get(placement_id, [])# list of stages changes
        current_name = helper.stage_name(stages, placement.get("stageId")) # on which stage candidate is now
        stage_names = [current_name]
        for row in history:
            stage_names.append(helper.stage_name(stages, row.get("toStageId")))
        for row in history:
            stage_names.append(helper.stage_name(stages, row.get("fromStageId")))

        # The highest stage reached (1 to 7).
        # give no. to each stage and takes the highest.
        levels = []
        for name in stage_names:
            level = helper.stage_to_level(name)
            if level:
                levels.append(level)
        stage_level = 1
        if levels:
            stage_level = max(levels)
        current_stage = stages.get(helper.id_as_text(placement.get("stageId"))) or {}
        is_final_stage = bool(current_stage.get("isTerminal"))
        if current_stage.get("terminalOutcome") == "hired" and is_final_stage:
            stage_level = constants.HIRED_LEVEL
        rejected = "reject" in current_name.lower()
        if current_stage.get("terminalOutcome") == "rejected" and is_final_stage:
            rejected = True

        # The reasons the candidate was rejected for.
        rejection_reasons = {str((placement.get("capturedDetails") or {}).get("rejectionReason") or "").lower()}
        for row in history:
            rejection_reasons.add(str((row.get("metadata") or {}).get("rejectionReason") or "").lower())
            if "existing-micro1-user" in str(row.get("note") or "").lower():
                rejection_reasons.add("existing-micro1-user")
        # early rejection - duplicate” or “underqualified”, or a rejection at the first two stages.       
        rejected_early = bool(rejection_reasons & constants.EARLY_REJECTION_REASONS)
        if rejected and stage_level <= constants.SHORTLIST_LEVEL:
            rejected_early = True

        candidates.append({
            "resume_id": resume_id,
            "job_id": job_id,
            "job": worked_jobs[job_id],
            "created_at": helper.to_date(placement.get("createdAt")),
            "resume": helper.make_resume(tm_data["resumes"][resume_id]),
            "stage_level": stage_level,
            "rejected_early": rejected_early,
            # true-passed, false- failed, none-notest or no result yet
            "test_result": helper.find_test_result(stage_names, stage_level, rejected, rejection_reasons),
            # reach stage 2 or higher and not rejected early.
            "shortlisted": stage_level >= constants.SHORTLIST_LEVEL and not rejected_early,
            #team review: 1.0 approved, 0.0 rejected or needs more info, None not reviewed.
            "approved": helper.find_approval(placement.get("reviewStatus")),
        })
    return {"candidates": candidates, "worked_jobs": worked_jobs, "assigned_jobs": assigned_jobs}


# ================================================================================================ THE TEXT MODEL
class Embedder:
    """Turns a text into numbers (a vector) so that two texts can be compared by meaning.  It uses a free model that runs on this computer.
    Every text is turned into numbers only once; the result is remembered."""
# used in build tm  profile , first call add text
# used in candidate match score , here cll vector of
    def __init__(self):
        try:
            from sentence_transformers  import SentenceTransformer  # tool
            self.model = SentenceTransformer("all-MiniLM-L6-v2") #model
        except Exception:
            sys.exit("This script needs sentence-transformers:  pip install sentence-transformers")
        self.vectors = {}

    def add_texts(self, texts):
        """Turns many texts into numbers in one go (faster than one by one)."""
        new_texts = sorted({text for text in texts if text and text not in self.vectors})
        if not new_texts:
            return
        new_vectors = self.model.encode(new_texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        for text, vector in zip(new_texts, new_vectors):
            self.vectors[text] = vector

    def vector_of(self, text):
        """The numbers of one text."""
        self.add_texts([text])
        return self.vectors[text]


# ================================================================================================ SCORE 3: CANDIDATE MATCH
def candidate_match_score(resume, job, embedder):
    """How well one resume matched the job it was sent for, from 0 to 100.
    Skills 40, experience 25, title 15, location 10, education 5, meaning 5.  A part with no data is left out and the others share its weight."""
    scores = {}

    if job["skills"]: # weight -40
        matching_skills = resume["skills"] & job["skills"]
        scores["skills"] = 100 * len(matching_skills) / len(job["skills"])

    if resume["years"] is not None and (job["min_years"] or job["max_years"]): #weight -25
        low = job["min_years"]
        high = None
        if job["max_years"] > job["min_years"]:
            high = job["max_years"]
        if resume["years"] < low:
            scores["experience"] = max(0.0, 100 - 25 * (low - resume["years"]))        # 25 points lost for each missing year
        elif high is not None and resume["years"] > high:
            scores["experience"] = max(0.0, 100 - 10 * (resume["years"] - high))       # 10 points lost for each extra year
        else:
            scores["experience"] = 100.0

    if resume["title_text"] and job["title"]: #weight - 15
        similarity = float(embedder.vector_of(resume["title_text"]) @ embedder.vector_of(job["title"]))
        scores["title"] = 100 * helper.scale_0_to_1(similarity, *constants.TITLE_SIMILARITY_RANGE)

    if job["cities"] and not job["remote"] and resume["city"]: #weight -10
        if resume["city"] in job["cities"]:
            scores["location"] = 100.0                              # the candidate lives in the job's city
        elif resume["relocation_cities"] & job["cities"]:
            scores["location"] = 70.0                               # the candidate is open to move there
        else:
            scores["location"] = 30.0

    if job["degree"] and resume["degree_rank"]: #weight -5
        if resume["degree_rank"] >= job["degree"]:
            scores["education"] = 100.0
        elif resume["degree_rank"] == job["degree"] - 1:
            scores["education"] = 60.0
        else:
            scores["education"] = 20.0

    if resume["text"]: #weight-5
        similarity = float(embedder.vector_of(resume["text"]) @ embedder.vector_of(helper.job_text(job)))
        scores["meaning"] = max(0.0, similarity) * 100

    weights = constants.CANDIDATE_MATCH_WEIGHTS
    total_weight = sum(weights[name] for name in scores)
    if total_weight == 0:
        return None
    return sum(weights[name] * scores[name] for name in scores) / total_weight


# ================================================================================================ SCORE 2: THE TM SCORE OF A GROUP
def calculate_group_score(group_candidates, group_type, group_value, tm_facts): #group type-role 
    """The TM score (0 to 1) of one group, for example the group "Backend" of the type "role".
    group_candidates are the TM's past candidates of this group.  tm_facts holds numbers that are the same for the whole TM."""
    job_ids = {candidate["job_id"] for candidate in group_candidates}
    factors = {}

    # How far the candidates got in the hiring stages (the stage reached divided by 7).
    factors["progress"] = helper.average_or_none([c["stage_level"] / constants.HIRED_LEVEL for c in group_candidates])
    # The share of candidates who passed the test or AI interview (only the ones with a known result).
    factors["test"] = helper.average_or_none([float(c["test_result"]) for c in group_candidates if c["test_result"] is not None])
    # The average candidate match score (score 3) divided by 100.
    factors["match"] = helper.average_or_none([c["match_score"] / 100 for c in group_candidates if c["match_score"] is not None])
    # The share approved by the team (only the candidates that were reviewed).
    factors["approval"] = helper.average_or_none([c["approved"] for c in group_candidates if c["approved"] is not None])
    # How few were rejected early: 1 means none.
    factors["early"] = helper.average_or_none([1.0 - c["rejected_early"] for c in group_candidates])
    # Candidates per job, compared with the TM's own typical number (1 is the most).
    candidates_per_job = len(group_candidates) / len(job_ids)
    factors["volume"] = min(candidates_per_job / tm_facts["typical_candidates_per_job"], 1.0)

    # Of the jobs assigned to the TM in this group, the share the TM sent candidates for.
    assigned_in_group = set()
    for job_id, job in tm_facts["assigned_jobs"].items():
        if job[group_type] == group_value:
            assigned_in_group.add(job_id)
    if assigned_in_group:
        factors["coverage"] = len(assigned_in_group & tm_facts["worked_job_ids"]) / len(assigned_in_group)
    else:
        factors["coverage"] = None

    # Speed: days from the job being created to the first candidate sent, compared with the TM's own typical days.
    days = []
    for job_id in job_ids:
        if job_id in tm_facts["days_to_first_submission"]:
            days.append(tm_facts["days_to_first_submission"][job_id])
    if days:
        factors["speed"] = float(np.clip(1 - np.median(days) / (2 * tm_facts["typical_days"]), 0, 1))
    else:
        factors["speed"] = None

    # The score: the weighted average of the factors that have data (a missing factor is left out and the others share its weight).
    weights = constants.TM_SCORE_WEIGHTS
    known = {}
    for name, value in factors.items():
        if value is not None:
            known[name] = value
    score = sum(weights[name] * known[name] for name in known) / sum(weights[name] for name in known)

    count = len(group_candidates)
    if count < 5:
        confidence = "Low"
    elif count <= 15:
        confidence = "Medium"
    else:
        confidence = "High"
    matches = [c["match_score"] for c in group_candidates if c["match_score"] is not None]
    average_match = None
    if matches:
        average_match = float(np.mean(matches))
    return {"candidates": count, "jobs": len(job_ids), "score": score, "confidence": confidence,
            "shortlisted_share": sum(c["shortlisted"] for c in group_candidates) / count, "average_match": average_match}


def build_tm_profile(prepared, embedder):#TELL WHAT TM IS GOOD AT
    """The profile of one TM: the TM score of every group the TM has worked in (score 2).
    A group is one role, one level, one city or one industry, for example "Backend" or "bangalore"."""
    candidates = prepared["candidates"]
    if not candidates:                  # no past candidates: there is nothing to learn from, so no job can be scored
        empty_groups = {group_type: {} for group_type in constants.GROUP_TYPES}#group- role, level,location,industry
        return {"groups": empty_groups, "typical_scores": {}, "good_skills": collections.Counter(), "past_candidates": 0}

    # Step 1: the match score (score 3) of every past candidate.
    texts = []
    for candidate in candidates:
        texts.append(candidate["resume"]["text"])
        texts.append(candidate["resume"]["title_text"])
    for job in prepared["worked_jobs"].values():
        texts.append(job["title"])
        texts.append(helper.job_text(job))
    embedder.add_texts(texts)
    for candidate in candidates:
        candidate["match_score"] = candidate_match_score(candidate["resume"], candidate["job"], embedder)

    # Step 2: numbers that are the same for the whole TM.
    candidates_by_job = collections.defaultdict(list)
    #sort the candidates by job
    for candidate in candidates:
        candidates_by_job[candidate["job_id"]].append(candidate)
    days_to_first_submission = {}       # for each job: days from the job being created to the first candidate sent
    for job_id, job_candidates in candidates_by_job.items():
        sent_dates = [c["created_at"] for c in job_candidates if c["created_at"]] # the dates at which candidates for this job were sent
        job_created = job_candidates[0]["job"]["created_at"] # the day job was created
        if sent_dates and job_created:# only continue if both exists
            days = (min(sent_dates) - job_created).total_seconds() / 86400
            if 0 <= days <= constants.MAX_DAYS_TO_FIRST_SUBMISSION:
                days_to_first_submission[job_id] = days       
    counts = [len(job_candidates) for job_candidates in candidates_by_job.values()] # how many candidates were sent for each job
    typical_days = 1.0
    if days_to_first_submission:
        typical_days = max(float(np.median(list(days_to_first_submission.values()))), 1.0)
    tm_facts = {"assigned_jobs": prepared["assigned_jobs"], "worked_job_ids": set(candidates_by_job),
                "days_to_first_submission": days_to_first_submission, "typical_days": typical_days,
                "typical_candidates_per_job": max(float(np.median(counts)), 1.0)}

    # Step 3: the TM score of every group.
    groups = {}
    for group_type in constants.GROUP_TYPES:
        candidates_by_group = collections.defaultdict(list)
        for candidate in candidates:
            group_value = candidate["job"][group_type]
            if group_value is not None:
                candidates_by_group[group_value].append(candidate)
        groups[group_type] = {}
        for group_value, group_candidates in candidates_by_group.items():
            groups[group_type][group_value] = calculate_group_score(group_candidates, group_type, group_value, tm_facts)

    # Step 4: the typical score of each group type: the middle score of the groups that have enough candidates.
    typical_scores = {}
    for group_type, type_groups in groups.items():
        scores = [g["score"] for g in type_groups.values()]
        if scores:
            typical_scores[group_type] = float(np.median(scores))

    # Step 5: the skills of the jobs where the TM's candidates did well.
    good_skills = collections.Counter()
    for candidate in candidates:
        did_well = (candidate["match_score"] or 0) >= constants.GOOD_MATCH_SCORE and not candidate["rejected_early"]
        if did_well or candidate["stage_level"] >= constants.CLIENT_SHORTLIST_LEVEL:
            good_skills.update(candidate["job"]["skills"])

    return {"groups": groups, "typical_scores": typical_scores, "good_skills": good_skills, "past_candidates": len(candidates)}


# ================================================================================================ SCORE 1: THE JOB FIT
def score_job_for_tm(job, profile):
    """How well one job fits one TM.  It returns: the fit (0 to 1, or None when it cannot be scored), the confidence,
    the score of each part, and the reasons in three lists: good (supports the fit), watch (a warning) and notes (neutral)."""
    part_scores = {}
    good, watch, notes = [], [], []

    # The parts role, level, location and industry: the TM's score in the job's group of that type.
    for group_type in constants.GROUP_TYPES:
        group_value = job[group_type]
        type_groups = profile["groups"][group_type]

        if group_value is None:         # the job does not say it, so the TM's typical score is used
            if group_type in profile["typical_scores"]:
                part_scores[group_type] = profile["typical_scores"][group_type]
                notes.append(f"The job does not say its {group_type}")
            continue
        if not type_groups:             # the TM has no history of this type at all
            continue

        words = helper.group_phrase(group_type, group_value)
        group = type_groups.get(group_value)
        if group is not None:
            part_scores[group_type] = group["score"]
            typical = profile["typical_scores"].get(group_type, group["score"])
            if group["score"] >= typical * 1.05:
                good.append(f"Did well on {words}")
            elif group["score"] <= typical * 0.9:
                watch.append(f"Weak results on {words}")
            else:
                notes.append(f"Average results on {words}")
        else:                           # the TM never worked on it, or with too few candidates: a trial
            part_scores[group_type] = constants.TRIAL_SCORE
            if group is None:
                watch.append(f"Has not worked on {words} before")
            else:
                watch.append(f"Very few candidates for {words} so far")

    # The skills part: how many of the job's skills appear in the jobs where the TM's candidates did well.
    # Skills read from the text need at least 3 found, otherwise one stray word could decide the score.
    has_enough_skills = len(job["skills"]) >= 3 or not job["skills_read_from_text"]
    if job["skills"] and profile["good_skills"] and has_enough_skills:
        known_skills = [skill for skill in job["skills"] if skill in profile["good_skills"]]
        part_scores["skills"] = len(known_skills) / len(job["skills"])
        if part_scores["skills"] >= 0.5:
            good.append(f"Knows {len(known_skills)} of the {len(job['skills'])} skills asked")
        else:
            watch.append(f"Knows only {len(known_skills)} of the {len(job['skills'])} skills asked")

    if not part_scores:
        return None, "Low", part_scores, good, watch, notes

    # The fit: the weighted average of the parts (a missing part is left out and the others share its weight).
    weights = constants.JOB_FIT_WEIGHTS
    fit = sum(weights[name] * part_scores[name] for name in part_scores) / sum(weights[name] for name in part_scores)

    # The confidence follows the number of candidates behind the role score.
    role_group = profile["groups"]["role"].get(job["role"])
    confidence = "Low"
    if role_group is not None:
        confidence = role_group["confidence"]
    return fit, confidence, part_scores, good, watch, notes
