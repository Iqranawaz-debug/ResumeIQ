"""Bundled fictional resume and job description for the one-click demo.

The resume is invented (no real person) and deliberately mixed: strong matches,
a related-but-different cloud platform, a missing certification, weak bullet
wording and an unreadable date, so every part of the analysis has something to show.
"""

SAMPLE_FILENAME = 'sample-resume-alex-rivera.txt'

SAMPLE_RESUME = """Alex Rivera
alex.rivera@example.invalid | +1 555 010 4477

Professional Summary
Backend engineer focused on payment systems and developer tooling.

Skills
Python, Django, FastAPI, PostgreSQL, Docker, Azure, REST APIs, Git, Pytest

Experience
Senior Software Engineer, Example Payments Inc
Mar 2021 - Present
Designed and built REST APIs in Python and FastAPI that process card refunds for 2 million customers.
Reduced average API response time by 35% by adding PostgreSQL indexes and query caching.
Worked on the CI pipelines and was responsible for Docker deployments on Azure.
Mentored two junior engineers through code reviews and pairing sessions.

Software Engineer, Example Retail Ltd
Jun 2018 - Feb 2021
Utilized Django in order to build internal inventory dashboards.
I helped with migrating legacy reports to PostgreSQL.

Software Engineering Intern, Example Labs
Summer 2017
Wrote Pytest suites for a data validation library.

Projects
Open-source rate limiter
Built a Python rate-limiting library with Redis support used in side projects.

Certifications
Microsoft Certified: Azure Developer Associate (2022)

Education
BSc Computer Science, Example State University, 2018
"""

SAMPLE_JOB_DESCRIPTION = """Senior Backend Engineer - Payments Platform

About us: We have been building payment products for 15 years.

Requirements:
- 5+ years of experience building backend services with Python
- Experience with AWS or similar cloud platforms
- Strong knowledge of PostgreSQL and Docker
- Hands-on experience with Kubernetes and Terraform
- Bachelor's degree in Computer Science or related field
- AWS certification

Responsibilities:
- Design and build REST APIs for payment processing
- Maintain CI pipelines and deployments for the platform
- Mentor junior engineers

Nice to have:
- Experience with Go and Redis

We offer flexible remote work and great benefits.
"""
