# Project constants

ALLOWED_EXTENSIONS = ["pdf", "docx"]
MAX_FILE_SIZE_MB = 10

ERROR_NO_FILE = "No file uploaded."
ERROR_INVALID_TYPE = "Invalid file type. Please upload a PDF or DOCX file."
ERROR_EMPTY_FILE = "The uploaded file is empty."
ERROR_FILE_TOO_LARGE = f"File size exceeds the {MAX_FILE_SIZE_MB}MB limit."

KNOWN_SKILLS = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang",
    "rust", "php", "ruby", "swift", "kotlin", "scala", "r", "matlab",
    # Frontend
    "react", "angular", "vue", "next.js", "redux", "html", "css",
    "tailwind css", "bootstrap", "jquery",
    # Backend / frameworks
    "node.js", "express", "django", "flask", "fastapi", "spring",
    "spring boot", ".net", "asp.net", "laravel", "ruby on rails",
    # Data / databases
    "sql", "mysql", "postgresql", "mongodb", "redis", "sqlite",
    "elasticsearch", "data analysis", "data science", "pandas", "numpy",
    "power bi", "tableau", "excel",
    # Cloud / devops
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins",
    "ci/cd", "linux", "git", "github", "gitlab", "bash",
    # AI / ML
    "machine learning", "deep learning", "tensorflow", "pytorch",
    "natural language processing", "computer vision",
    # Methodology / tools
    "agile", "scrum", "jira", "confluence", "rest api", "graphql",
    "microservices", "figma", "photoshop", "salesforce", "sap",
]

