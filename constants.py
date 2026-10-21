"""
constants.py  --  all the settings and fixed tables of the TM / job matching.  There is no function in this file.

The secret (the database connection string) is NOT here: it is in the .env file next to this file.
"""

import os

# ================================================================================================ 1. FOLDERS AND DATABASE
BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # the folder of this project
ENV_FILE = os.path.join(BASE_DIR, ".env")                   # the file that holds MONGO_URI (the connection string)
OUTPUT_DIR = os.path.join(BASE_DIR, "Output")               # the JSON results are saved here
DATABASE = "futurejobsProd"                                 # the name of the database

# ================================================================================================ 2. WHICH TMs AND JOBS TO COMPARE
# Two fixed lists of ids (hardcoded).  Every job in JOB_IDS is compared with every TM in TM_IDS.
# They hold 15 ids each as a start (the first 15 users and the first 15 jobs of the database).
# To compare other TMs or jobs, add, remove or replace ids here.
TM_IDS = [
    "6a2d0c703745637f90dee38b",     # Sanjay Patil
    "6a2695a02bad2cf61f628e17",     # Nabeel
    "6a27d02296858e49af79ef45",     # Mohan
    "6996fbf35ea274877d200857",     # Dominic Coutinho
    "6a15a7e8e816531924fb5a9e",     # sarswati thakur
    "69ecdaa7ac07cab87e9d887d",     # Vidhya TS
    "69ee14a99d2dd786607fc0f2",     # danish shaikh
    "69e07801e5433e23b5a29069",     # Jhalak
    "6a402b8847b883334710b350",     # Akshaj Malhotra - XII-C1
    "69f2ef12f8d1d504e747ba6b",     # latika gautam
    "6a030d5271a196dde7e65143",     # Nirupama Pradhan
    "6a5de8e99a7355de64960a26",     # Apurva Parulekar
    "6a23334558ece2465ab8cc5d",     # NAVIN KUMAR SINHA
    "6a5b825b39fda490ca64a7d8",     # Nishanth Nair
    "6a4fc8c0f472868867d43a8b",     # Biswa Ranjan Behera
]
JOB_IDS = [
    "69d0ff7ff8b9f71103b5094d",     # Digital Marketing Specialist
    "69d4b57e81ef06d5a1f88431",     # Brand & Strategy Professional
    "69858a044d176aedf2a415dc",     # SAP Senior TM Functional Consultant
    "6a2435c358ece2465ab980ba",     # Jr Software Engineer
    "6a51f8fdcf1d26b417d4f0c7",     # Jr Software Engineer (Sample JD)
    "69f8ecfd9a9168faba05c6af",     # Municipal Project Manager
    "6a6475167c19a0b245fb0641",     # Jr Software Engineer (Sample JD)
    "69930d0e5ea274877d1ee12d",     # SAP BW 4 HANA Consultant
    "6a15a3bde816531924fb5941",     # Jr Software Engineer (Sample JD)
    "69f7ef96b90cc55b98238304",     # <script>alert('XSS')</script>
    "6acf018fd32c8610423bb7e6",     # Engineer – Quantity Surveyor
    "699711385ea274877d2015b8",     # Head of Platform Engineering
    "69f9d7df9a9168faba0641a5",     # PHP Developer
    "69e1ed9d244df6c8d24cce58",     # Telesales
    "69284064167bb6fe1aa4f7c5",     # Support Executive
    "6a21664e1b2172791b94ba03",     # ServiceNow Architect
    "6a27fe5696858e49af7a9c33",     # Jr Software Engineer (Sample JD)
    "6a3f598bf64218254ebdb1d4",     # Jr Software Engineer (Sample JD)
    "69e338e7bde2a387f4674bc9",     # Senior Institutional Sales Executive
    "6997f4ef5ea274877d205354",     # SAS Fraud Management Specialist
    "693670826dc7bc87a4ae941e",     # Product Manager
    "69b7a41ab60886fc9efb10fe",     # UI/UX Designer
    "6acf6150c109e1d3158ad9a8",     # Jr Software Engineer (Sample JD)
    "69c2b3c2f1626a3326a7ca80",     # Talent Acquisition Recruiter
    "6a311574af1fed482d9e6dcb",     # Jr Software Engineer (Sample JD)
    "691fe68e039bf45a8c2e61c7",     # Senior Admission Counsellor
    "6a705f8c65d055d054b307b8",     # Frontend Software Engineer
    "68259acdbb242cc26ef822e3",     # Software Engineer
    "69ba478b520e835bc6232e85",     # Senior Backend Engineer
    "6a686710273dcbdf590aadda",     # Jr Software Engineer (Sample JD)
    "6a647e517c19a0b245fb5985",     # Jr Software Engineer (Sample JD)
    "69785f31a56892bf8c4e4d6f",     # Program Delivery Manager (PDM)
    "69959ec35ea274877d1f9eda",     # Senior / Lead OIC Supply Chain Developer
    "69e06a03244df6c8d24b7a08",     # Non -IT Recruiter
    "699582c85ea274877d1f7869",     # Animator
    "6a2ee8ab3745637f90dfb92b",     # Jr Software Engineer (Sample JD)
    "692176e311089369fe37850b",     # Account Executive
    "69f2231f409d8a95133594ea",     # Senior Manager or AGM – Marketing (Hospitality)
    "6a7372a9ce684609a9d5130d",     # Jr Software Engineer (Sample JD)
    "6a1d4457006fc24fb6f541c1",     # Jr Software Engineer (Sample JD)
    "69d8b20279a06d7c932d40dc",     # Technical Lead
    "6a0c850d6e7a0151430ca0d9",     # Jr Software Engineer (Sample JD)
    "6968b7d76c7553adbed63dec",     # Senior Backend Developer
    "6972f69ac436e1b80d438a54",     # Business Development Executive
    "6980f790e6306b03fc56b33f",     # Senior Data Consultant
    "69f36703982dd3a2f335bd45",     # Data Center Operations Engineer
    "69a04469ff4891f1f08b03c3",     # Land Officer
    "69e31a36bde2a387f4673aa7",     # Technical Lead
    "6a79e1b3e473ce7e75a403cc",     # Jr Software Engineer (Sample JD)
    "69cf45bb685bdf853ba5f15c",     # iOS Developer
]

# ================================================================================================ 3. THE SCORES (the list confirmed by the team)
# the four kinds of group a TM's results are split into (and the first four parts of the job fit)
GROUP_TYPES = ("role", "level", "location", "industry")

# score 1: how well a job fits a TM (each part is the TM's score in the group the job belongs to)
JOB_FIT_WEIGHTS = {"role": 40, "level": 25, "skills": 20, "location": 10, "industry": 5}
# score 2: how well a TM did in one group (one role, one level, one city or one industry)
TM_SCORE_WEIGHTS = {"progress": 25, "test": 20, "match": 15, "approval": 10, "early": 10, "coverage": 10, "volume": 5, "speed": 5}
# score 3: how well one candidate's resume matches the job it was sent for (0 to 100)
CANDIDATE_MATCH_WEIGHTS = {"skills": 40, "experience": 25, "title": 15, "location": 10, "education": 5, "meaning": 5}
TRIAL_SCORE = 0.40              # the score of a role / level / city / industry the TM has not worked on yet (a trial)  # a group with fewer candidates than this counts as a trial
GOOD_MATCH_SCORE = 60           # a candidate with a match score of at least this is a "good" candidate (used for the skill overlap)
CLIENT_SHORTLIST_LEVEL = 3      # a candidate who reached this stage (client shortlisted) is also a "good" candidate
TITLE_SIMILARITY_RANGE = (0.28, 0.96)    # a title similarity of 0.28 counts as 0 and of 0.96 counts as 1
MAX_DAYS_TO_FIRST_SUBMISSION = 120    # speed counts only when the first candidate was sent within this many days of the job being created
SHORTLIST_LEVEL = 2             # reaching this stage counts as shortlisted
TEST_LEVEL = 4                  # the stage of a test or AI interview
INTERVIEW_LEVEL = 5             # the stage of a real interview
HIRED_LEVEL = 7                 # the last stage: hired
# a candidate rejected for one of these reasons counts as an early rejection
EARLY_REJECTION_REASONS = {"existing-user", "duplicate", "underqualified", "overqualified", "existing-micro1-user", "invalid"}
# every job has its own stage names; these keywords put them on one scale of 1 to 7 (the first match wins)
STAGE_LEVELS = [
    (7, r"hired|joined|project started|payout"), (6, r"offer"),
    (5, r"interview scheduled|interview done|interview completed|technical round|functional round|hr round|client interview|final round|^interview$|round \d"),
    (4, r"\bai interview|certified|assessment|assignment|\btest\b"), (3, r"client shortlist"),
    (2, r"internal shortlist|inviter shortlist|profile submitted|^shortlisted$"),
    (1, r"sourced|applied|interested|job link|guest review|waiting|new stage|screen")]
# a degree as a number: a higher number is a higher degree
DEGREE_RANKS = {"high_school": 1, "intermediate": 2, "diploma": 2, "foundation": 2, "associates": 2, "bachelors": 3, "bachelor": 3,
               "masters": 4, "master": 4, "phd": 5}
# the experience levels of a job: Entry 0-2 years, Mid 3-6, Senior 7-11, Lead 12 or more
EXPERIENCE_LEVELS = ["Entry (0-2)", "Mid (3-6)", "Senior (7-11)", "Lead (12+)"]

# ================================================================================================ 4. ROLES, SKILLS AND CITIES
# the role of a job, found from keywords in its title: the first role that matches wins (the order matters: 'IT hardware sales' is a sales job)
ROLE_KEYWORDS = [
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
DEPARTMENT_TO_ROLE = {"IT_DEPARTMENT": "Software", "RESEARCH_AND_DEVELOPMENT": "Research & Development", "SALES": "Sales / BD",
                    "MARKETING_DEPARTMENT": "Marketing / Content", "FINANCE_AND_ACCOUNTS_DEPARTMENT": "Finance / Accounts",
                    "ADMINISTRATION": "Administration", "HUMAN_RESOURCE_DEPARTMENT": "HR / Recruiting",
                    "CUSTOMER_SERVICE_DEPARTMENT": "Customer Support", "LEGAL_DEPARTMENT": "Legal / Compliance"}
# skills written in different ways that mean the same thing
SKILL_SYNONYMS = {"js": "javascript", "ts": "typescript", "reactjs": "react", "react js": "react", "nodejs": "node", "node js": "node",
            "k8s": "kubernetes", "ml": "machine learning", "postgres": "postgresql", "mongo": "mongodb", "mongodb atlas": "mongodb",
            "aws cloud": "aws", "amazon web services": "aws", "gcp": "google cloud", "ms excel": "excel", "microsoft excel": "excel",
            "qa": "testing", "quality assurance": "testing", "selenium webdriver": "selenium", "rest api": "rest", "restful api": "rest",
            "rest apis": "rest", "dotnet": ".net", "dot net": ".net", "vuejs": "vue", "nextjs": "next", "next js": "next", "node.js": "node"}
# cities that count as the same place
CITY_GROUPS = {"delhi ncr": ["delhi", "new delhi", "noida", "greater noida", "gurgaon", "gurugram", "faridabad", "ghaziabad", "delhi ncr", "ncr"],
                 "bangalore": ["bangalore", "bengaluru", "bangaluru"], "mumbai": ["mumbai", "bombay", "navi mumbai", "thane"],
                 "chennai": ["chennai", "madras"], "kolkata": ["kolkata", "calcutta"], "hyderabad": ["hyderabad", "secunderabad"],
                 "pune": ["pune", "pune division"], "kochi": ["kochi", "cochin"], "mysore": ["mysore", "mysuru"],
                 "thiruvananthapuram": ["thiruvananthapuram", "trivandrum"]}
CITY_TO_GROUP = {}              # each city name and the group it belongs to, for example "gurugram" -> "delhi ncr"
for group_name in CITY_GROUPS:
    for city_name in CITY_GROUPS[group_name]:
        CITY_TO_GROUP[city_name] = group_name
# words that look like a location but are not a city
NOT_CITIES = {"india", "united states", "usa", "us", "uk", "remote", "anywhere", "global", "worldwide", "uae", "canada", "germany", "hybrid", "on-site", "onsite"}
