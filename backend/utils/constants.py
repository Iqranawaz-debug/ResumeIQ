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
        "confluence", "rest api", "graphql", "microservices", "figma",
        "photoshop", "salesforce", "sap",
    ],
}

KNOWN_SKILLS = [skill for skills in SKILL_CATEGORIES.values() for skill in skills]

