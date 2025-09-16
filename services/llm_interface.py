import json, re, requests
from config.config_loader import CONFIG


# This file is currently not in use but we can use as config-switchable without hardcoding anything.
# Hence you can use any LLM ypu want just add configs in config.yml and make it provider.
def build_prompt(nl: str) -> str:
    return f"""
You are a strict JSON generator. Given a recruiter's natural language query, output a single JSON
object with keys: title, seniority, must_have (list), any_of (list), location, min_years (int or null), raw_query.
If a field is missing, use null or [].
Return ONLY the JSON object, nothing else.

Query: \"{nl}\"
"""


def parse_with_llm(nl: str):
    """Switch between Ollama and Hugging Face based on config.yml"""
    provider = CONFIG.get("llm", {}).get("provider", "ollama")

    if provider == "ollama":
        if not CONFIG.get("ollama", {}).get("enabled", False):
            raise RuntimeError("Ollama disabled in config.yml")
        payload = {
            "model": CONFIG["ollama"]["model"],
            "prompt": build_prompt(nl),
            "max_tokens": 256
        }
        resp = requests.post(CONFIG["ollama"]["api_url"], json=payload, timeout=8)
        resp.raise_for_status()
        j = resp.json()
        if isinstance(j, dict) and "text" in j:
            m = re.search(r"\{.*\}", j["text"], flags=re.S)
            if m:
                return json.loads(m.group(0))
        return None

    elif provider == "huggingface":
        api_url = CONFIG["huggingface"]["api_url"]
        model = CONFIG["huggingface"]["model"]
        token = CONFIG["huggingface"]["api_key"]

        headers = {"Authorization": f"Bearer {token}"}
        payload = {"inputs": build_prompt(nl), "parameters": {"max_new_tokens": 256}}

        resp = requests.post(f"{api_url}/{model}", headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        j = resp.json()

        # HF returns list of dicts with "generated_text"
        if isinstance(j, list) and "generated_text" in j[0]:
            m = re.search(r"\{.*\}", j[0]["generated_text"], flags=re.S)
            if m:
                return json.loads(m.group(0))
        return None

    else:
        raise RuntimeError(f"Unknown LLM provider: {provider}")
