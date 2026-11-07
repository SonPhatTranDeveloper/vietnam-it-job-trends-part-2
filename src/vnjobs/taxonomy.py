"""Dictionaries and rules that turn raw posting fields into analysis features.

Everything that decides what counts as a technology, a role or a seniority level lives here,
as data, so a notebook never hides a definition in a chart cell. Change a rule here, re-run
``05-extract-features.py``, and every notebook follows.
"""

from __future__ import annotations

import re

# --- technologies ----------------------------------------------------------------------
# name -> (category, literal aliases). Aliases are matched on lower-cased title + description
# with word edges that treat ``+``, ``#`` and ``.`` as part of a word, so "java" does not match
# inside "javascript" and "c++" is its own term. Deliberately left out because they are too
# ambiguous without context: "go", "r", "c", "swift" (the bank network), "spark", "spring".
TECHS: dict[str, tuple[str, tuple[str, ...]]] = {
    # languages
    "Python": ("language", ("python",)),
    "Java": ("language", ("java",)),
    "JavaScript": ("language", ("javascript", "ecmascript")),
    "TypeScript": ("language", ("typescript",)),
    "C++": ("language", ("c++",)),
    "C#": ("language", ("c#",)),
    "PHP": ("language", ("php",)),
    "Go": ("language", ("golang",)),
    "Rust": ("language", ("rust",)),
    "Kotlin": ("language", ("kotlin",)),
    "Swift": ("language", ("swiftui", "swift programming", "swift language")),
    "Ruby": ("language", ("ruby",)),
    "Scala": ("language", ("scala",)),
    "Dart": ("language", ("dart",)),
    "Objective-C": ("language", ("objective-c", "objective c")),
    "Perl": ("language", ("perl",)),
    "Lua": ("language", ("lua",)),
    "Solidity": ("language", ("solidity",)),
    "SQL": ("language", ("sql", "t-sql", "pl/sql", "plsql")),
    "HTML/CSS": ("language", ("html", "html5", "css", "css3")),
    # web frameworks
    "React": ("framework", ("react", "reactjs", "react.js", "react js")),
    "Angular": ("framework", ("angular", "angularjs")),
    "Vue": ("framework", ("vue", "vue.js", "vuejs", "vue js")),
    "Next.js": ("framework", ("next.js", "nextjs")),
    "Node.js": ("framework", ("node.js", "nodejs", "node js", "expressjs", "express.js")),
    "NestJS": ("framework", ("nestjs", "nest.js")),
    "Spring": ("framework", ("spring boot", "springboot", "spring framework", "spring mvc")),
    ".NET": ("framework", (".net", "dotnet", "asp.net", ".net core", "vb.net")),
    "Django": ("framework", ("django",)),
    "Flask": ("framework", ("flask",)),
    "FastAPI": ("framework", ("fastapi",)),
    "Laravel": ("framework", ("laravel",)),
    "Ruby on Rails": ("framework", ("ruby on rails", "rails")),
    "jQuery": ("framework", ("jquery",)),
    "GraphQL": ("framework", ("graphql",)),
    "REST API": ("framework", ("restful", "rest api", "rest apis", "restful api")),
    "Microservices": ("framework", ("microservices", "microservice")),
    # mobile
    "Android": ("mobile", ("android",)),
    "iOS": ("mobile", ("ios",)),
    "Flutter": ("mobile", ("flutter",)),
    "React Native": ("mobile", ("react native",)),
    "Xamarin": ("mobile", ("xamarin",)),
    # data stores and messaging
    "MySQL": ("database", ("mysql", "mariadb")),
    "PostgreSQL": ("database", ("postgresql", "postgres")),
    "MongoDB": ("database", ("mongodb", "mongo")),
    "Redis": ("database", ("redis",)),
    "Oracle": ("database", ("oracle",)),
    "SQL Server": ("database", ("sql server", "mssql", "ms sql")),
    "Elasticsearch": ("database", ("elasticsearch", "elastic search", "opensearch")),
    "Kafka": ("database", ("kafka",)),
    "RabbitMQ": ("database", ("rabbitmq",)),
    "Cassandra": ("database", ("cassandra",)),
    "DynamoDB": ("database", ("dynamodb",)),
    "NoSQL": ("database", ("nosql",)),
    # cloud and devops
    "AWS": ("cloud", ("aws", "amazon web services")),
    "Azure": ("cloud", ("azure",)),
    "GCP": ("cloud", ("gcp", "google cloud")),
    "Alibaba Cloud": ("cloud", ("alibaba cloud", "aliyun")),
    "Docker": ("devops", ("docker",)),
    "Kubernetes": ("devops", ("kubernetes", "k8s")),
    "Terraform": ("devops", ("terraform",)),
    "Ansible": ("devops", ("ansible",)),
    "Jenkins": ("devops", ("jenkins",)),
    "CI/CD": ("devops", ("ci/cd", "ci-cd", "cicd", "github actions", "gitlab ci")),
    "Linux": ("devops", ("linux", "ubuntu", "centos")),
    "Git": ("devops", ("git", "github", "gitlab", "bitbucket")),
    "Nginx": ("devops", ("nginx",)),
    "Prometheus/Grafana": ("devops", ("prometheus", "grafana")),
    "Helm": ("devops", ("helm",)),
    # data and BI
    "Spark": ("data", ("apache spark", "pyspark")),
    "Airflow": ("data", ("airflow",)),
    "Hadoop": ("data", ("hadoop",)),
    "dbt": ("data", ("dbt",)),
    "Snowflake": ("data", ("snowflake",)),
    "BigQuery": ("data", ("bigquery",)),
    "ETL": ("data", ("etl", "elt")),
    "Data Warehouse": ("data", ("data warehouse", "datawarehouse", "data lake", "lakehouse")),
    "Power BI": ("data", ("power bi", "powerbi")),
    "Tableau": ("data", ("tableau",)),
    "Pandas/NumPy": ("data", ("pandas", "numpy")),
    # AI and ML
    "Machine Learning": ("ai", ("machine learning", "học máy")),
    "Deep Learning": ("ai", ("deep learning", "học sâu")),
    "NLP": ("ai", ("nlp", "natural language processing", "xử lý ngôn ngữ")),
    "Computer Vision": ("ai", ("computer vision", "thị giác máy tính", "opencv")),
    "PyTorch": ("ai", ("pytorch",)),
    "TensorFlow": ("ai", ("tensorflow", "keras")),
    "scikit-learn": ("ai", ("scikit-learn", "sklearn", "scikit learn")),
    "MLOps": ("ai", ("mlops",)),
    "Generative AI": ("llm", ("generative ai", "genai", "gen ai", "gen-ai", "generative-ai")),
    "LLM": ("llm", ("llm", "llms", "large language model", "large language models")),
    "GPT/OpenAI": ("llm", ("gpt", "chatgpt", "openai", "gpt-4", "gemini", "claude")),
    "LangChain": ("llm", ("langchain", "llamaindex", "llama-index")),
    "RAG": ("llm", ("rag", "retrieval augmented generation", "retrieval-augmented generation")),
    "AI Agents": ("llm", ("ai agent", "ai agents", "agentic", "multi-agent")),
    "Prompt Engineering": ("llm", ("prompt engineering", "prompt design")),
    "Vector DB": ("llm", ("vector database", "vector db", "pinecone", "milvus", "pgvector")),
    "Hugging Face": ("llm", ("hugging face", "huggingface")),
    # testing
    "Selenium": ("testing", ("selenium",)),
    "Cypress": ("testing", ("cypress",)),
    "Playwright": ("testing", ("playwright",)),
    "JMeter": ("testing", ("jmeter",)),
    "Postman": ("testing", ("postman",)),
    "Appium": ("testing", ("appium",)),
    "Jest/JUnit": ("testing", ("jest", "junit", "pytest", "testng")),
    "Automation Testing": ("testing", ("automation test", "automated test", "test automation")),
    # security
    "Pentest": ("security", ("penetration testing", "pentest", "pen test", "owasp")),
    "SIEM": ("security", ("siem", "splunk", "soc analyst")),
    "ISO 27001": ("security", ("iso 27001", "iso27001")),
    # enterprise and infrastructure
    "SAP": ("enterprise", ("sap",)),
    "Odoo": ("enterprise", ("odoo",)),
    "Salesforce": ("enterprise", ("salesforce",)),
    "Dynamics 365": ("enterprise", ("dynamics 365", "dynamics crm", "dynamics ax")),
    "ServiceNow": ("enterprise", ("servicenow",)),
    "Cisco/CCNA": ("infrastructure", ("cisco", "ccna", "ccnp")),
    "VMware": ("infrastructure", ("vmware", "vsphere")),
    "Active Directory": ("infrastructure", ("active directory",)),
    "Windows Server": ("infrastructure", ("windows server",)),
    "Fortinet/Palo Alto": ("infrastructure", ("fortinet", "fortigate", "palo alto")),
    # embedded and game
    "Unity": ("game", ("unity", "unity3d")),
    "Unreal": ("game", ("unreal engine", "unreal")),
    "Embedded/RTOS": ("embedded", ("rtos", "stm32", "arduino", "raspberry pi", "firmware")),
    "FPGA": ("embedded", ("fpga", "verilog", "vhdl")),
}

TECH_CATEGORY = {name: category for name, (category, _) in TECHS.items()}

_ALIAS_TO_TECH = {alias: name for name, (_, aliases) in TECHS.items() for alias in aliases}
_EDGE_BEFORE = r"(?<![a-z0-9_+#.])"
_EDGE_AFTER = r"(?![a-z0-9_+#])"
_TECH_PATTERN = re.compile(
    _EDGE_BEFORE
    + "("
    + "|".join(re.escape(alias) for alias in sorted(_ALIAS_TO_TECH, key=len, reverse=True))
    + ")"
    + _EDGE_AFTER
)


def find_techs(text: str) -> list[str]:
    """Find every technology named in a piece of lower-cased text.

    Args:
        text: Lower-cased title plus description (or the joined skill tags).

    Returns:
        The canonical technology names found, each once, in alphabetical order.
    """
    return sorted({_ALIAS_TO_TECH[m.group(1)] for m in _TECH_PATTERN.finditer(text)})


# --- roles -----------------------------------------------------------------------------
# Ordered: the first rule whose pattern matches the lower-cased title wins, so the specific
# roles come before the general ones ("full stack" before "developer").
ROLE_RULES: tuple[tuple[str, str], ...] = (
    (
        "ai_ml",
        r"\b(ai|a\.i\.|ml|machine learning|deep learning|nlp|llm|computer vision|data scientist|"
        r"mlops|prompt|generative|artificial intelligence|trí tuệ nhân tạo)\b",
    ),
    (
        "data",
        r"(data (engineer|analyst|analytics|architect|warehouse|platform|steward|governance)|"
        r"\bbi\b|business intelligence|etl|big data|dữ liệu|\bdba\b|database admin|"
        r"phân tích số liệu)",
    ),
    (
        "security",
        r"(security|bảo mật|an ninh|an toàn thông tin|cyber|pentest|\bsoc\b|infosec|"
        r"\bsiem\b|\bgrc\b)",
    ),
    (
        "devops_cloud",
        r"(devops|devsecops|\bsre\b|site reliability|cloud|infrastructure|hạ tầng|"
        r"platform engineer|kubernetes|\bk8s\b|release engineer|build engineer)",
    ),
    (
        "qa_test",
        r"(\bqa\b|\bqc\b|tester|testing|kiểm thử|kiểm tra phần mềm|quality assurance|"
        r"test engineer|automation test|sdet)",
    ),
    ("mobile", r"(android|\bios\b|flutter|react native|mobile|di động|swift|kotlin)"),
    ("fullstack", r"(full[- ]?stack)"),
    (
        "frontend",
        r"(front[- ]?end|\breact\b|\bangular\b|\bvue\b|web developer|ui developer|"
        r"javascript|typescript)",
    ),
    (
        "backend",
        r"(back[- ]?end|\bjava\b|\.net|\bphp\b|python|golang|\bgo\b developer|node\.?js|"
        r"\bruby\b|\bc#|c\+\+|\brust\b|laravel|spring)",
    ),
    ("game", r"(\bgame\b|unity|unreal)"),
    (
        "embedded_iot",
        r"(embedded|firmware|\biot\b|\bfpga\b|\bplc\b|nhúng|vi điều khiển|"
        r"hardware engineer|\bpcb\b|\bscada\b)",
    ),
    (
        "erp_consulting",
        r"(\bsap\b|\berp\b|odoo|salesforce|dynamics|servicenow|functional consultant|"
        r"technical consultant|it consultant|oracle (ebs|fusion|hcm))",
    ),
    (
        "ba_pm_product",
        r"(business analyst|\bba\b|project manager|product (owner|manager)|"
        r"scrum master|\bpm\b|\bpmo\b|program manager|delivery manager|"
        r"quản lý dự án|phân tích nghiệp vụ|technical writer|presales|pre-sales)",
    ),
    ("design", r"(\bui\b|\bux\b|ui/ux|designer|thiết kế đồ họa|graphic)"),
    (
        "it_support_infra",
        r"(it support|it helpdesk|helpdesk|help desk|hỗ trợ (kỹ thuật|it|người dùng)|"
        r"system admin|sysadmin|quản trị (hệ thống|mạng)|network|mạng|"
        r"it technician|desktop support|it admin|it officer|it staff|nhân viên it|"
        r"chuyên viên it|\bnoc\b|thực tập sinh it|it intern)",
    ),
    # Not software: generic technicians and electrical, mechanical or automation engineers.
    # Jev, which sees only the title, lets many of these through as "tech".
    (
        "technical_non_software",
        r"(kỹ thuật viên|nhân viên kỹ thuật|chuyên viên kỹ thuật|cán bộ kỹ thuật|"
        r"kĩ thuật|kỹ thuật|technician|hiện trường|field|"
        r"kỹ sư (điện|cơ|xây dựng|tự động|điều khiển|viễn thông)|electrical|"
        r"mechanical|automation|control engineer|service engineer|"
        r"production engineer|quality engineer|technical support|vận hành)",
    ),
    (
        "software_other",
        r"(developer|programmer|software|lập trình|phần mềm|\bdev\b|application|"
        r"architect|technical lead|tech lead|\bit engineer|công nghệ thông tin|"
        r"kỹ sư (cntt|it|phần mềm|hệ thống)|system engineer|solutions? engineer|\bit\b)",
    ),
)
_ROLE_PATTERNS = tuple((role, re.compile(pattern)) for role, pattern in ROLE_RULES)


def classify_role(title: str) -> str:
    """Assign a job title to a role family using the ordered rules.

    Args:
        title: The cleaned job title, in any case.

    Returns:
        The first matching role family, or ``"other"`` when no rule matches.
    """
    lowered = title.lower()
    for role, pattern in _ROLE_PATTERNS:
        if pattern.search(lowered):
            return role
    return "other"


# --- seniority -------------------------------------------------------------------------
# Order of levels, lowest first; also the order charts stack them in.
LEVELS = ("intern", "junior", "mid", "mid_senior", "senior", "lead", "manager", "unknown")

_TITLE_LEVEL_RULES: tuple[tuple[str, str], ...] = (
    ("intern", r"(\bintern(ship)?s?\b|thực tập|\btrainee\b)"),
    (
        "junior",
        r"(\bjunior\b|\bjr\.?\b|\bfresher\b|\bentry[- ]level\b|\bfresh graduate\b|mới tốt nghiệp)",
    ),
    (
        "manager",
        r"(\bmanager\b|\bdirector\b|\bhead of\b|\bvp\b|\bcto\b|\bchief\b|giám đốc|trưởng phòng)",
    ),
    (
        "lead",
        r"(\blead\b|\bprincipal\b|\bstaff\b engineer|\barchitect\b|trưởng nhóm|team leader|"
        r"tech lead)",
    ),
    ("senior", r"(\bsenior\b|\bsr\.?\b|\bsenior\b|cao cấp)"),
    ("mid", r"(\bmid[- ]?level\b|\bmedior\b|\bintermediate\b)"),
)
_TITLE_LEVELS = tuple((level, re.compile(pattern)) for level, pattern in _TITLE_LEVEL_RULES)

# Exact lower-cased career-level labels seen in the feed, in English and Vietnamese. Generic
# labels such as "Nhân viên" (staff) say nothing about level and are left out on purpose.
LABEL_LEVELS = {
    "intern": "intern",
    "thực tập, intern": "intern",
    "intern, apprentice": "intern",
    "sinh viên/ thực tập sinh": "intern",
    "entry level": "junior",
    "mới tốt nghiệp": "junior",
    "junior": "junior",
    "cấp độ không yêu cầu kinh nghiệm": "junior",
    "no requirements": "junior",
    "cấp trung cấp": "mid",
    "medior": "mid",
    "associate": "mid",
    "cộng sự": "mid",
    "medior-senior level": "mid_senior",
    "senior": "senior",
    "lead": "lead",
    "trưởng nhóm / giám sát": "lead",
    "team leader / supervisor": "lead",
    "quản lý": "manager",
    "điều hành": "manager",
    "chief": "manager",
    "director": "manager",
}

_YEARS_PATTERN = re.compile(r"^(\d{1,2})\+? years?$")
_MONTHS_PATTERN = re.compile(
    r"(?:monthsofexperience:\s*|^)(\d{1,3})\+?(?: months(?: of experience)?)?$"
)
EXPERIENCE_LEVEL_MONTHS = ((12, "junior"), (36, "mid"), (47, "mid_senior"))


def level_from_title(title: str) -> str | None:
    """Read a seniority level out of a job title.

    Args:
        title: The job title, in any case.

    Returns:
        The level named by the title, or ``None`` when the title names none.
    """
    lowered = title.lower()
    for level, pattern in _TITLE_LEVELS:
        if pattern.search(lowered):
            return level
    return None


def experience_months(labels: list[str]) -> int | None:
    """Pull a required-experience figure, in months, out of the feed's experience labels.

    Args:
        labels: Values such as ``"36 months of experience"``, ``"monthsOfExperience: 24"``
            or ``"2+ years"``.

    Returns:
        The smallest figure found, in months, or ``None`` when no label carries one.
    """
    found: list[int] = []
    for label in labels:
        text = label.strip().lower()
        years = _YEARS_PATTERN.match(text)
        if years:
            found.append(int(years.group(1)) * 12)
            continue
        months = _MONTHS_PATTERN.search(text)
        if months and "month" in text:
            found.append(int(months.group(1)))
    return min(found) if found else None


def level_from_months(months: int | None) -> str | None:
    """Map a required-experience figure to a level, as a last resort.

    Args:
        months: Required experience in months, or ``None``.

    Returns:
        ``junior`` up to a year, ``mid`` up to three, ``mid_senior`` up to four, ``senior``
        beyond; ``None`` when there is no figure.
    """
    if months is None:
        return None
    for limit, level in EXPERIENCE_LEVEL_MONTHS:
        if months <= limit:
            return level
    return "senior"


def classify_level(title: str, career_labels: list[str], months: int | None) -> tuple[str, str]:
    """Decide a posting's seniority and say which signal decided it.

    Title keywords win, then the board's own career-level label, then the required
    experience. Anything left is ``unknown`` rather than guessed.

    Args:
        title: The job title.
        career_labels: Career-level labels from ``position`` and ``org_tags``.
        months: Required experience in months, or ``None``.

    Returns:
        ``(level, source)`` where source is ``title``, ``label``, ``experience`` or ``none``.
    """
    from_title = level_from_title(title)
    if from_title:
        return from_title, "title"
    for label in career_labels:
        level = LABEL_LEVELS.get(label.strip().lower())
        if level:
            return level, "label"
    from_months = level_from_months(months)
    if from_months:
        return from_months, "experience"
    return "unknown", "none"


# --- work mode, city, company ----------------------------------------------------------
def work_mode(raw: str | None) -> str | None:
    """Normalise the feed's ``workPlace`` value.

    Args:
        raw: Value such as ``Onsite``, ``hybrid`` or ``REMOTE_ANY``.

    Returns:
        ``remote``, ``hybrid`` or ``onsite``; ``None`` when the value is empty or another kind
        (field work, offshore).
    """
    if not raw:
        return None
    lowered = raw.lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "remote" in lowered:
        return "remote"
    if "onsite" in lowered or "in-office" in lowered:
        return "onsite"
    return None


CITY_GROUPS = (
    ("Hồ Chí Minh", ("ho chi minh", "hồ chí minh", "hcm", "saigon", "sài gòn", "thu duc")),
    ("Hà Nội", ("hanoi", "hà nội", "ha noi")),
    ("Đà Nẵng", ("da nang", "đà nẵng")),
)


def city_group(raw: str | None) -> str:
    """Collapse the feed's many spellings of a city into the three big ones.

    Args:
        raw: The raw city string.

    Returns:
        ``Hồ Chí Minh``, ``Hà Nội``, ``Đà Nẵng``, ``Other`` or ``Unknown`` when empty.
    """
    if not raw:
        return "Unknown"
    lowered = raw.lower()
    for name, aliases in CITY_GROUPS:
        if any(alias in lowered for alias in aliases):
            return name
    return "Other"


_COMPANY_NOISE = re.compile(
    r"\b(công ty|cty|tnhh|cổ phần|cp|co\.?|ltd\.?|jsc|inc\.?|corp(oration)?|llc|pte|"
    r"vietnam|việt nam|vn|chi nhánh|branch)\b"
)
# Prefixes of the normalised name that mark a corporate group; the first match wins.
COMPANY_GROUPS = (
    ("FPT", ("fpt",)),
    ("Bosch", ("bosch",)),
    ("Viettel", ("viettel",)),
    ("Vingroup", ("vingroup", "vinfast", "vinhomes", "vinai", "vinmec", "vinsmart", "vinbigdata")),
    ("KMS", ("kms",)),
    ("VNG", ("vng",)),
    ("NashTech", ("nashtech",)),
    ("TMA", ("tma",)),
    ("CMC", ("cmc",)),
    ("MB Bank", ("ngân hàng tmcp quân đội", "mbbank", "mb bank")),
)


def company_key(raw: str | None) -> str | None:
    """Normalise a company name so spelling variants of one employer line up.

    Args:
        raw: The raw ``company.nameOrg`` value.

    Returns:
        A lower-cased name without legal suffixes, branch notes or punctuation, or ``None``
        for an empty name.
    """
    if not raw or not raw.strip():
        return None
    lowered = re.split(r"\s[-\u2013(]\s|\(|,", raw.lower())[0]
    cleaned = _COMPANY_NOISE.sub(" ", lowered)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip() or None


def company_group(key: str | None) -> str | None:
    """Map a normalised company name to a corporate group when it belongs to one.

    Args:
        key: Output of :func:`company_key`.

    Returns:
        The group name, or ``None``.
    """
    if not key:
        return None
    for group, prefixes in COMPANY_GROUPS:
        if key.startswith(prefixes):
            return group
    return None


BANK_PATTERN = re.compile(
    r"(ngân hàng|\bbank\b|bank$|techcombank|vpbank|mbbank|vietcombank|"
    r"tpbank|hdbank|acb\b|vib\b|shb\b|ocb\b|msb\b|lpbank|vietinbank)"
)
AGENCY_PATTERN = re.compile(
    r"(recruit|staffing|headhunt|talent|reeracoen|nodeflair|robert walters|"
    r"michael page|manpower|adecco|aloha consulting|amaris|community|"
    r"đúng người đúng việc|hr consult|human resource)"
)


# --- salary ----------------------------------------------------------------------------
USD_TO_VND = 25_000  # one fixed rate for every year, so changes in the rate never move a trend
MIN_MONTHLY_VND = 3_000_000  # below this a parsed figure is almost surely a unit mistake
MAX_MONTHLY_VND = 600_000_000
_NEGOTIABLE = re.compile(
    r"(thỏa thuận|thoả thuận|cạnh tranh|negotiable|competitive|hấp dẫn|attractive|not disclosed|"
    r"undisclosed)"
)
_NUMBER = re.compile(
    r"(\d+(?:\.\d+)?e[+-]?\d+|\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)\s*"
    r"(tr|triệu|mil|m|million|k|nghìn)?\b"
)
_USD_MARK = re.compile(r"(usd|\$|us\$)")
_YEAR_MARK = re.compile(r"(năm|year|annual|/yr|p\.a\.)")
_HOUR_MARK = re.compile(r"(hour|giờ|/h\b)")
_UNIT_FACTOR = {
    "tr": 1e6,
    "triệu": 1e6,
    "mil": 1e6,
    "m": 1e6,
    "million": 1e6,
    "k": 1e3,
    "nghìn": 1e3,
}
MILLION_SHORTHAND_BELOW = 1000  # a bare "15.0 (VND per MONTH)" means fifteen million


def _to_number(token: str) -> float:
    """Parse ``10.000.000``, ``1,500``, ``2.5`` or ``2.0e7`` into a float.

    Args:
        token: A numeric token with optional thousand separators, decimals or an exponent.

    Returns:
        The number.
    """
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        return float(re.sub(r"[.,]", "", token))
    return float(token.replace(",", "."))


def _salary_values(lowered: str) -> list[float]:
    """Read up to two figures from a salary text, applying a unit given on only one of them.

    Args:
        lowered: The lower-cased salary text.

    Returns:
        The figures in the text's own currency and period (at most two).
    """
    pairs = [(_to_number(n), _UNIT_FACTOR.get(u)) for n, u in _NUMBER.findall(lowered)][:2]
    # In "15 - 25 triệu" only the last figure carries the unit; it applies to both.
    shared = next((factor for _, factor in reversed(pairs) if factor), None)
    values = [value * (factor or shared or 1) for value, factor in pairs]
    bare = not any(factor for _, factor in pairs)
    if bare and values and max(values) < MILLION_SHORTHAND_BELOW and "vnd" in lowered:
        values = [value * 1e6 for value in values]
    return values


def _monthly_scale(lowered: str, low: float) -> float:
    """Work out the multiplier that turns a figure into VND per month.

    Args:
        lowered: The lower-cased salary text.
        low: The smaller figure, in the text's own units.

    Returns:
        The multiplier. VND labelled "a year" that is already a plausible monthly figure is
        taken as monthly, because the boards mislabel it.
    """
    usd = bool(_USD_MARK.search(lowered))
    scale = USD_TO_VND if usd else 1
    if _YEAR_MARK.search(lowered) and (usd or low / 12 * scale < MIN_MONTHLY_VND <= low):
        scale = scale / 12 if usd else scale
    elif _YEAR_MARK.search(lowered):
        scale = scale / 12
    return scale


def parse_salary(text: str | None) -> tuple[float | None, float | None, bool]:
    """Turn a free-text salary into a monthly VND range.

    Args:
        text: Salary text such as ``8 Tr - 15 Tr VND`` or ``$1,500 - $2,500``.

    Returns:
        ``(low, high, negotiable)``: the range in VND per month (``None`` when no usable
        figure was found) and whether the text only says "negotiable", "competitive" or "not
        disclosed". USD is converted at ``USD_TO_VND``; yearly figures are divided by twelve;
        hourly figures are dropped.
    """
    if not text:
        return None, None, False
    lowered = text.lower()
    values = [] if _HOUR_MARK.search(lowered) else _salary_values(lowered)
    if not values:
        return None, None, bool(_NEGOTIABLE.search(lowered))
    scale = _monthly_scale(lowered, min(values))
    low, high = min(values) * scale, max(values) * scale
    if not (MIN_MONTHLY_VND <= low <= MAX_MONTHLY_VND):
        return None, None, False
    return low, high, False


# --- languages, degree, sectors, benefits ----------------------------------------------
# Each language flag fires when the title or description *mentions* the language or its
# certificate. A mention is not always a requirement, so the notebooks call it "mentions".
LANGUAGE_PATTERNS = {
    "japanese": re.compile(r"(japanese|tiếng nhật|nhật ngữ|jlpt|bridge se|\bbse\b|comtor|[぀-ヿ])"),
    "english": re.compile(r"(english|tiếng anh|ielts|toeic|toefl)"),
    "korean": re.compile(r"(korean|tiếng hàn|topik|[가-힯])"),
    "chinese": re.compile(r"(chinese|tiếng trung|tiếng hoa|mandarin|\bhsk\b)"),
}


def find_languages(text: str) -> dict[str, bool]:
    """Say which foreign languages a piece of lower-cased text mentions.

    Args:
        text: Lower-cased title plus description.

    Returns:
        ``{"japanese": ..., "english": ..., "korean": ..., "chinese": ...}``.
    """
    return {name: bool(pattern.search(text)) for name, pattern in LANGUAGE_PATTERNS.items()}


# Lowest first: when a posting accepts several levels, its minimum is the lowest it lists.
DEGREE_RULES = (
    ("high_school", ("high school", "trung học", "thpt")),
    (
        "associate_or_certificate",
        ("associate", "cao đẳng", "professional certificate", "trung cấp"),
    ),
    ("bachelor", ("bachelor", "đại học", "university", "engineer's degree")),
    ("master", ("master", "thạc sĩ", "postgraduate")),
)


def minimum_degree(labels: list[str]) -> str | None:
    """Read the lowest degree a posting accepts from its education labels.

    Args:
        labels: Values such as ``"credentialCategory: bachelor degree"`` or
            ``"alternateName: Đại học"``.

    Returns:
        ``high_school``, ``associate_or_certificate``, ``bachelor`` or ``master``; ``None``
        when no label names a degree.
    """
    joined = " ".join(labels).lower()
    for degree, words in DEGREE_RULES:
        if any(word in joined for word in words):
            return degree
    return None


# Industry tags differ by board (Vietnamese on CareerBuilder, English on LinkedIn), so they
# are grouped into sectors by keyword; one tag can belong to several sectors.
SECTOR_RULES = (
    (
        "Banking & finance",
        (
            "bank",
            "ngân hàng",
            "financ",
            "tài chính",
            "fintech",
            "insurance",
            "bảo hiểm",
            "securities",
            "chứng khoán",
            "investment",
            "payment",
        ),
    ),
    (
        "IT services & software",
        (
            "it services",
            "software",
            "phần mềm",
            "cntt",
            "it - ",
            "information technology",
            "consulting",
            "tư vấn",
            "computer",
            "internet",
            "technology",
            "công nghệ thông tin",
        ),
    ),
    ("Telecom", ("telecom", "viễn thông")),
    (
        "Manufacturing & electronics",
        (
            "electrical",
            "điện",
            "electronic",
            "mechanical",
            "cơ khí",
            "manufactur",
            "sản xuất",
            "automotive",
            "ô tô",
            "auto",
            "industrial",
            "semiconductor",
            "hardware",
            "machinery",
        ),
    ),
    (
        "Retail & e-commerce",
        (
            "retail",
            "bán lẻ",
            "e-commerce",
            "ecommerce",
            "thương mại điện tử",
            "consumer",
            "fmcg",
            "wholesale",
        ),
    ),
    ("Logistics & transport", ("logistics", "transport", "vận tải", "shipping", "supply chain")),
    ("Healthcare & pharma", ("health", "y tế", "pharma", "dược", "medical", "biotech")),
    ("Education", ("education", "giáo dục", "e-learning")),
    (
        "Media, games & ads",
        ("game", "media", "entertainment", "advertising", "quảng cáo", "marketing", "truyền thông"),
    ),
    (
        "Energy, construction & property",
        (
            "energy",
            "năng lượng",
            "construction",
            "xây dựng",
            "real estate",
            "bất động sản",
            "oil",
            "utilities",
        ),
    ),
)


def sectors_of(industries: list[str]) -> list[str]:
    """Group a posting's industry tags into sectors.

    Args:
        industries: The ``INDUSTRIES`` tag values.

    Returns:
        The sectors any tag belongs to, each once; ``["Other"]`` when none match and tags exist,
        ``[]`` when there are no tags.
    """
    if not industries:
        return []
    joined = " | ".join(industries).lower()
    found = [name for name, words in SECTOR_RULES if any(word in joined for word in words)]
    return found or ["Other"]


BENEFIT_WORDS = {
    "insurance": ("bảo hiểm", "insurance"),
    "training": ("đào tạo", "training"),
    "salary_review": ("tăng lương", "salary review"),
    "bonus": ("thưởng", "bonus"),
    "health_care": ("sức khỏe", "healthcare", "health care"),
    "travel": ("du lịch", "travel"),
    "annual_leave": ("nghỉ phép", "annual leave"),
    "laptop": ("laptop",),
    "allowance": ("phụ cấp", "allowance"),
    "uniform": ("đồng phục", "uniform"),
    "sport_club": ("sport", "thể thao"),
}


def benefits_of(tags: list[str]) -> list[str]:
    """Normalise a posting's ``COMPANY_BENEFITS`` tags.

    Args:
        tags: Benefit tags in Vietnamese or English.

    Returns:
        The canonical benefit names present, each once.
    """
    joined = " | ".join(tags).lower()
    return [name for name, words in BENEFIT_WORDS.items() if any(w in joined for w in words)]
