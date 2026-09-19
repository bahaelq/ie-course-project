"""Extract a job posting from a URL: download the page, let the LLM fill the fields.

Usage: uv run python -m ie_course.job_url https://example.com/jobs/123
"""

import ipaddress
import json
import socket
import sys
import urllib.request
from urllib.parse import urlparse

from lxml import html as lxml_html

from ie_course.llm_client import configured_client, extract_json_payload, request_json

PROMPT = """Extract this job posting into JSON with the keys:
title, company, location, employment_type, salary, description,
responsibilities, requirements, required_skills, preferred_skills, benefits
(the last five are lists of strings). Use null or [] if unknown. Return only JSON.

Text:
{text}"""


def check_public_url(url: str) -> None:
    """Raise ValueError unless the URL is http(s) and points to a public host."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Please enter a valid http(s) link.")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror:
        raise ValueError("Could not resolve this address.") from None
    if not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("Only public web addresses are allowed.")


def fetch_text(url: str) -> str:
    check_public_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(request, timeout=20).read(3_000_000)
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
