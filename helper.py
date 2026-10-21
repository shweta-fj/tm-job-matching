"""
helper.py  --  all the small helper functions of the project.

A helper function does one small job: it cleans a text, converts a value, finds something in a text, reads from the database
or saves a file.  matching_engine.py and main.py use these functions for the real steps.  The fixed tables they need
(keywords, synonyms and so on) are in constants.py.
"""

import datetime
import json
import os
import re

import numpy as np

import constants


# ================================================================================================ 1. THE .env FILE AND THE DATABASE
def load_env(path):
    """Reads the lines KEY=VALUE of the .env file into the environment.  A value that is already set in the environment is kept."""
    if not os.path.isfile(path):
        return
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def to_object_id(value):
    """A 24-character id text as a real MongoDB ObjectId.  The database stores ids as ObjectId, so plain text would match nothing."""
    try:
        from bson import ObjectId
    except ImportError:
        return str(value)
    if re.fullmatch(r"[0-9a-fA-F]{24}", str(value)):
        return ObjectId(value)
    return value


def find_all(database, collection_name, query, fields=None):
    """All the records of one collection that match the query, as a list.  'fields' limits which fields are read."""
    return list(database[collection_name].find(query, fields))


def find_by_ids(database, collection_name, id_texts, field_name="_id"):
    """The records whose field (the record id by default) is one of the given ids.  No ids means no records, without asking the database."""
    if not id_texts:
        return []
    query = {field_name: {"$in": [to_object_id(one_id) for one_id in id_texts]}}
    return find_all(database, collection_name, query)


def id_as_text(value):
    """Any database id as plain text (the {"$oid": ...} form of an exported file is handled too)."""
    if isinstance(value, dict):
        value = value.get("$oid")
    if value is None:
        return None
    return str(value)


def unique_values(placements, field_name):
    """The different values (as text) of one field, for example "jobId", over all the placements.  A placement is one candidate sent for one job."""
    values = set()
    for placement in placements:
        if placement.get(field_name):
            values.add(id_as_text(placement.get(field_name)))
    return list(values)


def find_owner(placement, member_to_user):
    """The TM who sent this candidate: through a workspace membership (a guest id) or directly (addedBy)."""
    guest_id = id_as_text(placement.get("submittedByGuestId"))
    if guest_id:
        return member_to_user.get(guest_id)
    return id_as_text(placement.get("addedBy"))


# ================================================================================================ 2. CLEANING TEXTS
def to_date(value):
    """A database date as a normal date without a time zone.  None when the date is missing or not readable."""
    if isinstance(value, datetime.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, dict):
        value = value.get("$date")
    if not value:
        return None
    try:
        date = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return date.replace(tzinfo=None)


def clean_skill(skill):
    """A skill name in one standard form, so that "JS", "Node.js" and "javascript" are compared as equal."""
    if isinstance(skill, dict):
        skill = skill.get("name")
    text = str(skill or "").lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"\.js\b", "js", text)
    text = re.sub(r"[^a-z0-9+#. ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return constants.SKILL_SYNONYMS.get(text, text)


def clean_city(location):
    """The city of a location text in one standard form (Gurugram and Noida both become "delhi ncr").  None when there is no city."""
    first_part = re.split(r"[,/|(]", str(location or "").lower().strip())[0].strip()
    city = constants.CITY_TO_GROUP.get(first_part, first_part)
    if city == "" or city in constants.NOT_CITIES:
        return None
    return city


def scale_0_to_1(value, low, high):
    """Puts a value on a scale of 0 to 1: 'low' becomes 0, 'high' becomes 1, anything outside is cut to 0 or 1."""
    return float(np.clip((value - low) / (high - low), 0, 1))


def average_or_none(values):
    """The average of a list of numbers.  None when the list is empty."""
    if len(values) == 0:
        return None
    return float(np.mean(values))


# ================================================================================================ 3. STAGES OF A CANDIDATE
def stage_name(stages, stage_id):
    """The name of a stage, or an empty text when the stage is not known."""
    stage = stages.get(id_as_text(stage_id)) or {}
    return str(stage.get("name") or "")


def stage_to_level(name):
    """A stage name as a level from 1 to 7 (1 = sourced ... 7 = hired).  None for a rejected stage or an unknown name."""
    text = str(name or "").lower().strip()
    if text == "" or "reject" in text:
        return None
    for level, keywords in constants.STAGE_LEVELS:
        if re.search(keywords, text):
            return level
    return None


def find_test_result(stage_names, stage_level, rejected, rejection_reasons):
    """True if the candidate passed the test or AI interview, False if failed it, None if there is no test or no result yet."""
    levels = [stage_to_level(name) for name in stage_names]
    took_test = constants.TEST_LEVEL in levels or "failed_ai_interview" in rejection_reasons
    if not took_test:
        return None
    for name in stage_names:
        if "certified" in name.lower():
            return True
    if stage_level >= constants.INTERVIEW_LEVEL:
        return True
    if "failed_ai_interview" in rejection_reasons:
        return False
    if rejected and stage_level == constants.TEST_LEVEL:
        return False
    return None


def find_approval(review_status):
    """The team review as a number: 1.0 approved, 0.0 rejected or needs more info, None when there is no review."""
    status = str(review_status or "").lower()
    if status == "approved":
        return 1.0
    if status in ("rejected", "needs_more_info"):
        return 0.0
    return None


# ================================================================================================ 4. JOBS AND RESUMES
def find_role(title, category_text="", department_code=None):
    """The role of a job (Sales, Backend, Healthcare ...).  It is found from the title, then the category text, then the department."""
    for text in (str(title or "").lower(), str(category_text or "").lower()):
        if text == "":
            continue
        for role_name, keywords in constants.ROLE_KEYWORDS:
            if re.search(keywords, text):
                return role_name
    return constants.DEPARTMENT_TO_ROLE.get(department_code, "Other")


def find_experience_level(min_years, max_years, words=""):
    """Entry, Mid, Senior or Lead.  It is found from the years the job asks, or from words such as "Mid Level"."""
    levels = constants.EXPERIENCE_LEVELS
    if min_years or max_years:
        years = min_years or 0
        if years <= 2:
            return levels[0]
        if years <= 6:
            return levels[1]
        if years <= 11:
            return levels[2]
        return levels[3]
    text = str(words or "").lower()
    if text == "":
        return None
    if re.search(r"intern|fresher|entry|junior|\bjr\b|trainee|graduate|beginner", text):
        return levels[0]
    if re.search(r"lead|principal|staff|head|director|architect|manager|executive", text):
        return levels[3]
    if re.search(r"senior|\bsr\b", text):
        return levels[2]
    if re.search(r"mid|intermediate|associate|experienced", text):
        return levels[1]
    return None


def make_skill_pattern(skill_list):
    """One search pattern that finds any skill of the list inside a text.  Longer skills come first, so "machine learning" wins over "learning"."""
    skills = sorted(skill_list, key=len, reverse=True)
    if len(skills) == 0:
        return None
    names = "|".join(re.escape(skill) for skill in skills)
    return re.compile(r"(?<![a-z0-9+#.])(" + names + r")(?![a-z0-9+#])")


def longest_first(skill):
    """The sort key that puts the longest skill name first (and the same lengths in alphabetical order)."""
    return (-len(skill), skill)


def find_skills_in_text(text, skill_pattern):
    """The skills mentioned in a text (at most 15, the longest names first).  Empty when there is no pattern."""
    if skill_pattern is None:
        return set()
    found = set()
    for match in skill_pattern.finditer(text.lower()):
        found.add(match.group(1))
    return set(sorted(found, key=longest_first)[:15])


def make_job(raw_job, skill_pattern=None):
    """One job of the database as a simple record: title, skills, years asked, cities, role, level, industry and so on."""
    experience = raw_job.get("experience") or {}
    skill_names = (raw_job.get("mustHaveSkills") or []) + (raw_job.get("coreSkills") or []) + (raw_job.get("mandatorySkills") or [])
    skills = set()
    for name in skill_names:
        skills.add(clean_skill(name))
    skills.discard("")

    title = raw_job.get("jobTitle") or ""
    responsibilities = " ".join(str(item) for item in raw_job.get("primaryResponsibilities") or [])
    description = (raw_job.get("summary") or "") + " " + responsibilities

    # a job that lists no skills gets them from its title and description
    skills_read_from_text = False
    if len(skills) == 0 and skill_pattern is not None:
        skills = find_skills_in_text(title + " " + description, skill_pattern)
        skills_read_from_text = True

    cities = []
    for location in raw_job.get("geographicJobLocations") or []:
        city = clean_city(location)
        if city:
            cities.append(city)

    industry = None
    for item in raw_job.get("industry") or []:
        if str(item).strip():
            industry = str(item).strip().lower()
            break

    qualifications = raw_job.get("educationalQualifications") or {}
    degree_name = str(qualifications.get("degreeType") or "").lower()
    work_mode = str(raw_job.get("workMode") or raw_job.get("jobLocation") or "").upper()
    min_years = experience.get("min") or 0
    max_years = experience.get("max") or 0

    first_city = None
    if cities:
        first_city = cities[0]

    return {"job_id": id_as_text(raw_job["_id"]), "title": title, "skills": skills, "skills_read_from_text": skills_read_from_text,
            "min_years": min_years, "max_years": max_years, "cities": set(cities), "remote": "REMOTE" in work_mode,
            "degree": constants.DEGREE_RANKS.get(degree_name), "description": description, "created_at": to_date(raw_job.get("createdAt")),
            "role": find_role(title, "", raw_job.get("jobDepartment")),
            "level": find_experience_level(experience.get("min"), experience.get("max")),
            "location": first_city, "industry": industry}


def make_resume(raw_resume):
    """One resume of the database as a simple record: skills, titles, years of experience, city, education."""
    skills = set()
    for skill in raw_resume.get("skills") or []:
        skills.add(clean_skill(skill))
    analysed = raw_resume.get("analysedSkills") or {}
    for group in ("basic", "medium", "advanced"):
        for skill in analysed.get(group) or []:
            skills.add(clean_skill(skill))
    jobs_held = raw_resume.get("employmentHistory") or []
    for job in jobs_held:
        for skill in job.get("skillsUsedInRole") or []:
            skills.add(clean_skill(skill))
    skills.discard("")

    # the job titles: the current one and the last three
    titles = [(raw_resume.get("currentCompanyDetails") or {}).get("designation")]
    for job in jobs_held[:3]:
        titles.append(job.get("designation"))
    titles = [title.strip() for title in titles if title and title.strip()]

    total = raw_resume.get("totalExperience") or {}
    years = None
    if total:
        years = (total.get("years") or 0) + (total.get("months") or 0) / 12
    if years == 0 and jobs_held:
        years = None                    # 0 years next to a job history means "not filled in"

    degree_rank = 0
    for education in raw_resume.get("educationalBackground") or []:
        rank = constants.DEGREE_RANKS.get(str(education.get("educationType") or "").lower(), 0)
        degree_rank = max(degree_rank, rank)

    relocation_cities = set()
    for place in raw_resume.get("relocationDetails") or []:
        city = clean_city(place)
        if city:
            relocation_cities.add(city)

    work_text = " ".join(str(job.get("workExperienceDescription") or "") for job in jobs_held)
    all_text = " ".join(titles) + " " + " ".join(sorted(skills)) + " " + work_text
    return {"skills": skills, "title_text": " | ".join(dict.fromkeys(titles)), "years": years,
            "city": clean_city(raw_resume.get("currentLocation")), "relocation_cities": relocation_cities,
            "degree_rank": degree_rank or None, "text": all_text[:3000]}


def job_text(job):
    """The text of a job (title, skills and description) used to compare its meaning with a resume."""
    return (job["title"] + ". " + " ".join(sorted(job["skills"])) + ". " + job["description"])[:1500]


# ================================================================================================ 5. RESULTS
def best_first(item):
    """The sort key of a (fit, entry) pair: the higher fit comes first, and a TM that could not be scored (fit None) comes last."""
    fit = item[0]
    if fit is None:
        return 1
    return -fit


def short_reason(good, watch, notes):
    """One short reason for a TM: the best reason that supports the fit, and the main warning, joined in one line."""
    parts = []
    if good:
        parts.append(good[0])
    if watch:
        parts.append(watch[0])
    if not parts and notes:
        parts.append(notes[0])
    return "; ".join(parts)


def group_phrase(group_type, value):
    """The words that name a group in a reason, for example "Backend jobs" or "jobs in bangalore"."""
    if group_type == "role":
        return f"{value} jobs"
    if group_type == "level":
        return f"{value} level jobs"
    if group_type == "location":
        return f"jobs in {value}"
    return f"{value} industry jobs"


def explain_calculation(part_scores):
    """Shows how the percentage is made from the scores of the parts (role, level, skills, location, industry).
    Each score is rounded to 2 decimals, then multiplied by the weight of its part (this gives the points of the part).
    The points are added up and divided by the total weight of the parts that exist.
    It returns the scores, the points, the totals, the result and the percentage.  With no scores it returns empty values."""
    weights = constants.JOB_FIT_WEIGHTS
    scores = {}
    points = {}
    total_points = 0.0
    total_weight = 0
    for part_name in weights:                       # the same order every time: role, level, skills, location, industry
        if part_name not in part_scores:
            continue                                # a part with no data is left out, and the others share its weight
        score = round(part_scores[part_name], 2)
        weight = weights[part_name]
        part_points = round(score * weight, 2)
        scores[part_name] = score
        points[part_name] = f"{score:.2f} x {weight} = {part_points:.2f}"
        total_points += part_points
        total_weight += weight

    if total_weight == 0:
        return {"fit": None, "percentage": None, "scores": {}, "points": {}, "total_points": None, "total_weight": None, "result": None}
    total_points = round(total_points, 2)
    fit = total_points / total_weight
    percentage = int(round(100 * fit))
    return {"fit": fit, "percentage": percentage, "scores": scores, "points": points, "total_points": total_points,
            "total_weight": total_weight, "result": f"{total_points:.2f} / {total_weight} = {percentage}%"}


def save_job_file(job, ranked_tms):
    """Saves the result of one job as a JSON file in the Output folder: the job name, then every TM (best first) with the
    percentage and a short reason.  Returns the file path."""
    clean_title = re.sub(r"[^\w\-]+", "_", str(job["title"] or "no_title")).strip("_")[:40]
    path = os.path.join(constants.OUTPUT_DIR, f"{clean_title}_{job['job_id']}.json")
    data = {"job_name": job["title"], "job_id": job["job_id"], "tms": ranked_tms}
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    return path
