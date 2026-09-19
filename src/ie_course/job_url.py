"""Extract a job posting from a URL: download the page, let the LLM fill the fields.

Usage: uv run python -m ie_course.job_url https://example.com/jobs/123
"""

import json
import sys
import urllib.request

from lxml import html as lxml_html

from ie_course.llm_client import configured_client, extract_json_payload, request_json

PROMPT = """Extract this job posting into JSON with the keys:
title, company, location, employment_type, salary, description,
responsibilities, requirements, required_skills, preferred_skills, benefits
(the last five are lists of strings). Use null or [] if unknown. Return only JSON.

Text:
{text}"""


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(request, timeout=20).read()
    tree = lxml_html.fromstring(page)
    for tag in tree.xpath("//script | //style | //nav | //footer"):
        tag.drop_tree()
    return " ".join(tree.text_content().split())


def extract_job(url: str) -> dict:
    text = fetch_text(url)[:12000]
    config, _ = configured_client()
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": PROMPT.format(text=text)}],
        "temperature": 0.0,
    }
    _, body, _ = request_json(
        str(config["base_url"]).rstrip("/") + "/chat/completions", str(config["api_key"]), payload
    )
    parsed, _ = extract_json_payload(body["choices"][0]["message"]["content"])
    return parsed



if __name__ == "__main__":
    print(json.dumps(extract_job(sys.argv[1]), indent=2, ensure_ascii=False))
