# services/jobs.py
JOBS = [
    {"id": "job1", "title": "Senior Java Developer", "location": "Pune", "skills": ["Java", "Spring Boot", "AWS"]},
    {"id": "job2", "title": "Data Scientist", "location": "Bangalore", "skills": ["Python", "TensorFlow", "PyTorch"]}
]


def list_jobs():
    return JOBS


def get_job(job_id):
    for j in JOBS:
        if j["id"] == job_id:
            return j
    return None
