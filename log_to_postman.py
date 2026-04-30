#!/usr/bin/env python3
"""log_to_postman.py

A tiny utility that converts server logs (in the format shown in the
question) into a Postman collection JSON that can be imported directly.

Usage::
    python log_to_postman.py [-i INPUT_LOG] [-o OUTPUT_JSON]

If ``-i`` is omitted the script reads from STDIN.  The generated collection
uses a ``{{baseUrl}}`` variable for the host so the user can set it in
Postman’s environment.

The parser looks for two kinds of lines:

1. Request log – contains ``请求URI:`` and optionally ``参数:`` with a JSON
   payload.  When a payload is present we assume a POST request; otherwise a
   GET request.
2. Response log – the next line that contains ``返回数据：``.  The JSON after
   the colon is stored as an example response body.

Each extracted request becomes an ``item`` in the Postman collection.

The script is deliberately simple – it does not depend on any third‑party
library and works on both Windows and Unix shells.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Regular expressions to capture parts of the log lines
REQ_RE = re.compile(r"请求URI:(?P<uri>[^,]+)(?:,.*)?参数:(?P<params>{.*})", re.S)
REQ_GET_RE = re.compile(r"请求URI:(?P<uri>[^,]+)")
RESP_RE = re.compile(r"返回数据：(?P<resp>{.*})", re.S)


def parse_logs(lines):
    """Parse the raw log lines and return a list of request dictionaries.

    Each dict contains ``uri``, ``method``, ``body`` (optional) and ``response``
    (optional).
    """
    requests = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Try POST‑like lines first (contain 参数)
        m = REQ_RE.search(line)
        if m:
            uri = m.group("uri").strip()
            body = json.loads(m.group("params"))
            method = "POST"
            # Look ahead for a response line
            response = None
            if i + 1 < len(lines):
                m_resp = RESP_RE.search(lines[i + 1])
                if m_resp:
                    try:
                        response = json.loads(m_resp.group("resp"))
                    except json.JSONDecodeError:
                        response = None
                    i += 1  # consume response line
            requests.append({"uri": uri, "method": method, "body": body, "response": response})
            i += 1
            continue
        # Fallback to GET‑like lines (no 参数)
        m = REQ_GET_RE.search(line)
        if m:
            uri = m.group("uri").strip()
            method = "GET"
            # Look ahead for response (optional)
            response = None
            if i + 1 < len(lines):
                m_resp = RESP_RE.search(lines[i + 1])
                if m_resp:
                    try:
                        response = json.loads(m_resp.group("resp"))
                    except json.JSONDecodeError:
                        response = None
                    i += 1
            requests.append({"uri": uri, "method": method, "body": None, "response": response})
        i += 1
    return requests


def build_postman_collection(requests, collection_name="Generated from logs"):
    collection = {
        "info": {
            "name": collection_name,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": "{{uuid}}"
        },
        "item": []
    }
    for req in requests:
        url_path = req["uri"].lstrip('/')
        item = {
            "name": f"{req['method']} {url_path}",
            "request": {
                "method": req["method"],
                "header": [
                    {"key": "Content-Type", "value": "application/json"}
                ],
                "url": {
                    "raw": f"{{{{baseUrl}}}}/{url_path}",
                    "host": ["{{baseUrl}}"],
                    "path": url_path.split('/')
                }
            },
            "response": []
        }
        if req["body"] is not None:
            item["request"]["body"] = {
                "mode": "raw",
                "raw": json.dumps(req["body"], ensure_ascii=False, indent=2),
                "options": {"raw": {"language": "json"}}
            }
        # Add an example response if we captured one
        if req["response"] is not None:
            item["response"].append({
                "name": "Example response",
                "originalRequest": item["request"],
                "status": "OK",
                "code": 200,
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": json.dumps(req["response"], ensure_ascii=False, indent=2)
            })
        collection["item"].append(item)
    return collection


def main():
    parser = argparse.ArgumentParser(description="Convert server logs to a Postman collection JSON.")
    parser.add_argument("-i", "--input", type=Path, help="Log file (default: STDIN)")
    parser.add_argument("-o", "--output", type=Path, default=Path("postman_collection.json"), help="Output JSON file")
    args = parser.parse_args()

    if args.input:
        raw = args.input.read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    lines = raw.splitlines()
    requests = parse_logs(lines)
    collection = build_postman_collection(requests)
    args.output.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Postman collection written to {args.output}")

if __name__ == "__main__":
    main()
