"""
constants.py  --  every setting and every fixed table of the TM / job matching.  No logic here except loading the .env file.

The secrets (database connection string) are NOT in this file: they are in the .env file next to it.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "Output")


# ================================================================================================ 1. SECRETS (from the .env file)
def _load_env(path):
    """Reads KEY=VALUE lines of the .env file into the environment (a value already set in the environment wins)."""
    if not os.path.isfile(path):
        return
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(os.path.join(BASE_DIR, ".env"))
MONGO_URI = os.environ.get("MONGO_URI", "")
DATABASE = os.environ.get("DATABASE", "futurejobsProd")

# ================================================================================================ 2. WHAT TO RUN
# No TM id and no job id is typed here: both lists come from the database (the users and jobdescriptions collections, in database order).
# Each run takes the next BATCH_JOBS job ids that are not done yet, and compares each of those jobs with ALL the TM ids.
BATCH_JOBS = 15
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")   # the job ids already done, so the next run starts after them (delete it to start again)

# ================================================================================================ 3. THE SCORES (the list confirmed by the team)
JOB_FIT_WEIGHTS = {"role": 40, "level": 25, "skills": 20, "location": 10, "industry": 5}                              # score 1
TM_WEIGHTS = {"progress": 25, "test": 20, "match": 15, "approval": 10, "early": 10, "coverage": 10, "volume": 5, "speed": 5}    # score 2
MATCH_WEIGHTS = {"skills": 40, "experience": 25, "title": 15, "location": 10, "education": 5, "meaning": 5}            # score 3 (0-100)
UNSEEN_SCORE = 0.40             # a role / level / location / industry the TM has not worked on (a trial)
MIN_GROUP_CANDIDATES = 5        # a group with fewer real candidates than this counts as not worked on
GOOD_MATCH = 60                 # a candidate with a match score of at least this is a "good" candidate for the skill overlap
CLIENT_LEVEL = 3                # reaching this stage level (client shortlisted) also makes a candidate "good" for the skill overlap
TITLE_ANCHORS = (0.28, 0.96)    # title similarity that counts as 0 and as 1
SPEED_WINDOW_DAYS = 120         # speed counts only when the first submission came within this many days of the job being created
SHORTLIST_LEVEL = 2             # reaching this stage level counts as shortlisted
TOP_LEVEL = 7
EARLY_REASONS = {"existing-user", "duplicate", "underqualified", "overqualified", "existing-micro1-user", "invalid"}
STAGE_LADDER = [                # every job has its own stage names; they are put on one ladder, first match wins
    (7, r"hired|joined|project started|payout"), (6, r"offer"),
    (5, r"interview scheduled|interview done|interview completed|technical round|functional round|hr round|client interview|final round|^interview$|round \d"),
    (4, r"\bai interview|certified|assessment|assignment|\btest\b"), (3, r"client shortlist"),
    (2, r"internal shortlist|inviter shortlist|profile submitted|^shortlisted$"),
    (1, r"sourced|applied|interested|job link|guest review|waiting|new stage|screen")]
DEGREE_RANK = {"high_school": 1, "intermediate": 2, "diploma": 2, "foundation": 2, "associates": 2, "bachelors": 3, "bachelor": 3,
               "masters": 4, "master": 4, "phd": 5}
LEVELS = ["Entry (0-2)", "Mid (3-6)", "Senior (7-11)", "Lead (12+)"]

# ================================================================================================ 4. ROLES, SKILLS AND CITIES
# the role of a job, from its title: first match wins (the order matters: 'IT hardware sales' is a sales job)
ROLE_RULES = [
    ("AI Data / Language", r"annotat|data label|generalist \(|ai data|bilingual|linguist|language expert|translat|transcri|native .*speak"),
    ("Sales / BD", r"\bsales\b|pre.?sales|business development|\bbde?\b|account (manager|executive)|key account|channel partner|relationship manager|telesales|inside sales"),
    ("Customer Support", r"customer (support|service|success|care|relationship)|support (executive|engineer|associate|specialist|analyst)|call cent|help ?desk|service desk|\bbpo\b|\bcsr\b|technical support"),
    ("Product / Project", r"product manager|project manager|program manager|scrum|product owner|business analyst|delivery manager|project coordinator|project lead|\bpmo\b|technical project"),
    ("Design / Creative", r"\bux\b|\bui\b|graphic|visual design|product design|motion|video (editor|creator)|multimedia|animator|illustrat|creative|designer(?! engineer)|photograph|art director"),
    ("Hardware / VLSI", r"\brtl\b|vlsi|silicon|asic|fpga|embedded|firmware|hardware|\bchip\b|\bpcb\b|design verification|physical design|device driver|linux kernel"),
    ("Security", r"security|cyber|penetration|\bsoc\b|infosec"),
    ("QA / Testing", r"\bqa\b|\btest|quality assurance|\bsdet\b|automation engineer"),
    ("Mobile", r"android|\bios\b|mobile|flutter|react native"),
    ("Full Stack", r"full.?stack|\bmern\b|\bmean\b"),
    ("Frontend", r"front.?end|ui developer|react(?!.?native)|angular|\bvue\b"),
    ("Backend", r"back.?end|\bjava\b|python developer|\.net|dotnet|\bnode|golang|\bphp\b|django|spring|\bapi\b"),
    ("DevOps / Cloud", r"devops|cloud|\bsre\b|site reliability|it infrastructure|infrastructure engineer|platform engineer|kubernetes|sysadmin|system admin|network engineer|\bdba\b|database admin"),
    ("Data / AI", r"data scien|machine learning|\bml\b|\bai\b|gen ?ai|generative|data engineer|data analy|analytics|\bnlp\b|\bllm|research engineer|computer vision|deep learning|\bbi\b|power bi|tableau|qlik|looker|model evaluation|business intelligence|statistician|snowflake|\bdbt\b|\betl\b|databricks|\bspark\b|\bdata\b"),
    ("ERP / CRM", r"\bsap\b|oracle|salesforce|\berp\b|crm (developer|consultant|engineer|administrator|admin)|dynamics|servicenow"),
    ("Software", r"software|developer|programmer|\bsde\b|tech(nical)? lead|engineering manager|solutions? architect|staff engineer|\bit (manager|executive|support)|web ?master|\bgame\b|unity|unreal|graphics"),
    ("Healthcare / Medical", r"\bnurs|doctor|physician|surgeon|medical|clinic|healthcare|health care|hospital|pharmac|dentist|paramedic|therap|psycholog|psychiatr|radiolog|lab technician|caregiver|patient|\bmbbs\b|ayush|physio|dietician|nutritionist"),
    ("Education / Training", r"teacher|lecturer|professor|faculty|tutor|instructor|\btrainer|academic|educator|curriculum|\bschool\b"),
    ("Legal / Compliance", r"lawyer|advocate|attorney|legal|paralegal|compliance|\bcounsel|\bcouncel|\blaw\b|company secretary"),
    ("Marketing / Content", r"marketing|\bseo\b|content|copywrit|social media|brand|growth|\bcrm\b|public relations|\bpr\b|advertis|campaign|influencer|journalist|editor|\bwriter\b|community"),
    ("HR / Recruiting", r"\bhr\b|human resource|recruit|talent|sourcer|payroll|people (partner|operations)|\bhrbp\b|learning and development"),
    ("Finance / Accounts", r"financ|account(ant|s|ing)|audit|\btax|\bca\b|bookkeep|treasury|banking|bancassurance|credit|\bloan|insurance|underwrit|actuar|investment|equity|\bfp&a\b|billing|collections"),
    ("Operations / Logistics", r"operations|logistic|supply chain|warehouse|inventory|procurement|purchas|dispatch|fleet|transport|store manager|facility|stores|vendor|import|export|shipping|land acquisition|leasing|e-?commerce"),
    ("Manufacturing / Engineering", r"mechanical|civil|electrical|electronics|production|manufactur|\bplant\b|quality engineer|maintenance|\bcnc\b|machinist|welder|technician|site engineer|construction|architect|surveyor|\bbim\b|hvac|autocad|chemical|process engineer|\bqc\b|automobile|automotive|mechatronic|instrumentation|textile|garment|\bplm\b|\behs\b"),
    ("Hospitality / Retail", r"\bchef\b|\bcook\b|hotel|hospitality|restaurant|waiter|barista|retail|cashier|merchandis|front desk|housekeeping|travel|tour|cabin crew|salon|beauty"),
    ("Management / Consulting", r"strategy|management consult|business consult|\bconsultant\b|chief|founder|\bceo\b|\bcoo\b|general manager|\bvp\b|director|engineering leader"),
    ("Administration", r"admin|receptionist|secretary|office|data entry|executive assistant|coordinator|\bclerk|back office|\bpa\b"),
]
DEPARTMENT_ROLES = {"IT_DEPARTMENT": "Software", "RESEARCH_AND_DEVELOPMENT": "Research & Development", "SALES": "Sales / BD",
                    "MARKETING_DEPARTMENT": "Marketing / Content", "FINANCE_AND_ACCOUNTS_DEPARTMENT": "Finance / Accounts",
                    "ADMINISTRATION": "Administration", "HUMAN_RESOURCE_DEPARTMENT": "HR / Recruiting",
                    "CUSTOMER_SERVICE_DEPARTMENT": "Customer Support", "LEGAL_DEPARTMENT": "Legal / Compliance"}
SYNONYMS = {"js": "javascript", "ts": "typescript", "reactjs": "react", "react js": "react", "nodejs": "node", "node js": "node",
            "k8s": "kubernetes", "ml": "machine learning", "postgres": "postgresql", "mongo": "mongodb", "mongodb atlas": "mongodb",
            "aws cloud": "aws", "amazon web services": "aws", "gcp": "google cloud", "ms excel": "excel", "microsoft excel": "excel",
            "qa": "testing", "quality assurance": "testing", "selenium webdriver": "selenium", "rest api": "rest", "restful api": "rest",
            "rest apis": "rest", "dotnet": ".net", "dot net": ".net", "vuejs": "vue", "nextjs": "next", "next js": "next", "node.js": "node"}
CITY_VARIANTS = {"delhi ncr": ["delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram", "faridabad", "ghaziabad", "delhi ncr", "ncr"],
                 "bangalore": ["bangalore", "bengaluru", "bangaluru"], "mumbai": ["mumbai", "bombay", "navi mumbai", "thane"],
                 "chennai": ["chennai", "madras"], "kolkata": ["kolkata", "calcutta"], "hyderabad": ["hyderabad", "secunderabad"],
                 "pune": ["pune", "pune division"], "kochi": ["kochi", "cochin"], "mysore": ["mysore", "mysuru"],
                 "thiruvananthapuram": ["thiruvananthapuram", "trivandrum"]}
CITY_OF = {v: canon for canon, vs in CITY_VARIANTS.items() for v in vs}
NOT_CITIES = {"india", "united states", "usa", "us", "uk", "remote", "anywhere", "global", "worldwide", "uae", "canada", "germany", "hybrid", "on-site", "onsite"}

