"""
main.py  --  compares every job with every talent manager (TM) and saves the results.

The steps:
    1. read the connection string from the .env file and connect to the database
    2. take the TM ids (TM_IDS) and the job ids (JOB_IDS) of constants.py, and read those TMs and jobs from the database
    3. build the profile of each TM once (how well the TM did in each role, level, city and industry)
    4. for each job: score every TM for that job (a percentage and the reasons), and save the result in one JSON file
       Output/<job_title>_<job_id>.json.  Nothing is shown on the screen.

RUN   python main.py        (needs  pip install numpy sentence-transformers pymongo)
"""

import os

import constants
import helper
from matching_engine import Embedder, MongoSource, build_tm_profile, prepare_candidates, score_job_for_tm


def compare_job_with_all_tms(job, tm_profiles): # job- one job record., tm_profiles take two things user(tm records from db) , profile(what script learned about the tm)
    """Scores every TM for one job.  tm_profiles is a list of (user, profile) pairs.
    It returns one entry per TM, the best fit first: the TM name, the percentage and one short reason."""
    results = []                        # a list of (fit, entry) pairs per tm 
    for user, profile in tm_profiles:
        fit, confidence, part_scores, good, watch, notes = score_job_for_tm(job, profile)

        if fit is None:
            percentage = None
            reason = "Could not be scored: this TM has no past candidates to learn from"
        else:
            percentage = int(round(100 * fit))
            reason = helper.short_reason(good, watch, notes)

        entry = {"tm_name": user.get("name"),
                 "tm_id": helper.id_as_text(user["_id"]),     # the id is kept because some TMs have no name in the database
                 "percentage": percentage,
                 "reason": reason}
        results.append((fit, entry))

    results.sort(key=helper.best_first)         # best Tm first for each job

    ranked = []
    for fit, entry in results:
        ranked.append(entry)
    return ranked


def main():
    # Step 1: connect to the database.
    helper.load_env(constants.ENV_FILE)
    connection_string = os.environ.get("MONGO_URI", "")
    source = MongoSource(connection_string, constants.DATABASE)

    # Step 2: read the TMs and the jobs of the two lists in constants.py.
    #get_skill_list()- make list of most commen skills 
    #make_skill_pattern- turn them into serach pattern (used to find those skills that are not define in jd)
    skill_pattern = helper.make_skill_pattern(source.get_skill_list()) 
    # it reads the tm id list 
    users = source.get_users(constants.TM_IDS)
    # it take job id and then reads job from database and convert it into title, skills, role, level, location, industry(by make_job)
    # and add to the jobs list.
    jobs = []
    for raw_job in source.get_jobs(constants.JOB_IDS):
        jobs.append(helper.make_job(raw_job, skill_pattern))

    # Step 3: build the profile of each TM once; it is used for every job.
    embedder = Embedder()
    #create output folder if not exist
    os.makedirs(constants.OUTPUT_DIR, exist_ok=True)
    # empty list- it holds one profile for each TM
    tm_profiles = []
    # goes through tm one by one
    for user in users:
        #id_as_text turns the id into plain text first then it reads everything about the tm from database.
        tm_data = source.get_tm_data(helper.id_as_text(user["_id"]))
        # turn the data into list of past candidates each with there sections.
        prepared = prepare_candidates(tm_data, skill_pattern)
        # build the Tm profile
        tm_profiles.append((user, build_tm_profile(prepared, embedder)))

    # Step 4: compare each job with all the TMs and save one JSON file per job.
    for job in jobs:
        #score every tm for the particular jobs and return them best first, each with the name, percentage and short reason
        ranked = compare_job_with_all_tms(job, tm_profiles)
        helper.save_job_file(job, ranked)


if __name__ == "__main__":
    main()
