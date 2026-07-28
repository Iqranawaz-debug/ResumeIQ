# Project constants

ALLOWED_EXTENSIONS = ["pdf", "docx"]
MAX_FILE_SIZE_MB = 10

ERROR_NO_FILE = "No file uploaded."
ERROR_INVALID_TYPE = "Invalid file type. Please upload a PDF or DOCX file."
ERROR_EMPTY_FILE = "The uploaded file is empty."
ERROR_FILE_TOO_LARGE = f"File size exceeds the {MAX_FILE_SIZE_MB}MB limit."

SKILL_CATEGORIES = {
    "Languages": [
        "python", "java", "javascript", "typescript", "c++", "c#", "golang",
        "rust", "php", "ruby", "swift", "kotlin", "scala", "r", "matlab",
    ],
    "Frontend": [
        "react", "angular", "vue", "next.js", "redux", "html", "css",
        "tailwind css", "bootstrap", "jquery",
    ],
    "Backend": [
        "node.js", "express", "django", "flask", "fastapi", "spring",
        "spring boot", ".net", "asp.net", "laravel", "ruby on rails",
    ],
    "Cloud": ["aws", "azure", "gcp"],
    "Cybersecurity": [
        "splunk", "microsoft sentinel", "elastic siem", "siem",
        "sigma rule authoring", "mitre att&ck", "att&ck mapping", "mitre",
        "threat hunting", "threat intelligence", "incident response",
        "incident reporting", "digital forensics", "host forensics",
        "memory analysis", "malware analysis", "malware sandboxing",
        "phishing analysis", "vulnerability assessment",
        "penetration testing", "network security", "network protocols",
        "active directory", "endpoint detection and response", "edr",
        "crowdstrike", "microsoft defender for endpoint", "wireshark",
        "nessus", "burp suite", "kali linux", "volatility", "velociraptor",
        "kape", "cloudtrail", "azure ad", "iso 27001", "nist",
        "vulnerability scanning", "log analysis", "security operations",
        "soc", "firewall configuration", "ids/ips",
    ],
    "Database": [
        "sql", "mysql", "postgresql", "mongodb", "redis", "sqlite",
        "elasticsearch",
    ],
    "Data & AI": [
        "data analysis", "data science", "pandas", "numpy", "power bi",
        "tableau", "excel", "machine learning", "deep learning",
        "tensorflow", "pytorch", "natural language processing",
        "computer vision",
    ],
    "Tools": [
        "docker", "kubernetes", "terraform", "jenkins", "ci/cd", "linux",
        "git", "github", "gitlab", "bash", "agile", "scrum", "jira",
        "confluence", "rest api", "graphql", "microservices", "salesforce",
        "sap",
    ],
    "Design": [
        "figma", "sketch", "adobe xd", "invision", "wireframing",
        "prototyping", "user research", "usability testing",
        "interaction design", "design systems", "ui design", "ux design",
        "adobe illustrator", "adobe premiere", "graphic design",
    ],
    "Healthcare": [
        "patient care", "iv therapy", "wound care", "vital signs",
        "ehr", "emr", "cpr", "bls", "phlebotomy",
        "medication administration", "clinical documentation", "triage",
        "infection control", "patient assessment", "hipaa",
    ],
    "Marketing": [
        "seo", "sem", "google analytics", "content marketing",
        "email marketing", "social media marketing", "ppc",
        "brand strategy", "market research", "copywriting", "google ads",
        "hubspot", "mailchimp", "growth marketing",
    ],
    "Sales": [
        "crm", "lead generation", "cold calling", "account management",
        "negotiation", "sales pipeline", "b2b sales", "b2c sales",
        "upselling", "quota attainment",
    ],
    "Finance": [
        "financial modeling", "bookkeeping", "accounts payable",
        "accounts receivable", "gaap", "quickbooks", "financial analysis",
        "budgeting", "forecasting", "auditing", "tax preparation",
        "reconciliation", "cpa",
    ],
    "Legal": [
        "contract review", "legal research", "litigation", "compliance",
        "due diligence", "regulatory compliance", "legal writing",
        "case management", "paralegal", "intellectual property",
    ],
    "Education": [
        "curriculum development", "lesson planning", "classroom management",
        "student assessment", "differentiated instruction", "iep",
        "special education", "tutoring", "instructional design",
    ],
    "Customer Service": [
        "customer support", "help desk", "zendesk", "ticketing systems",
        "customer satisfaction", "technical support", "live chat support",
        "call center", "conflict resolution",
    ],
    "Human Resources": [
        "recruiting", "talent acquisition", "onboarding",
        "employee relations", "performance management", "hris",
        "benefits administration", "payroll", "workforce planning",
    ],
}

KNOWN_SKILLS = [skill for skills in SKILL_CATEGORIES.values() for skill in skills]

