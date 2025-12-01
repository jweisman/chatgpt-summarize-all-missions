import os
import time
import argparse
import pandas as pd
from typing import List
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

MODEL_DEFAULT = os.getenv("LLM_MODEL", "gpt-4.1")  # override with env if you like

SYSTEM_TONE = """You are an expert retail agronomist.
Write a season-oriented summary in 2–3 sentences. Be concrete and concise.
- Track EARLY vs LATE season dynamics.
- Cover when relevant: emergence, weeds, disease (incl. Tar Spot), nutrient deficiencies, insect damage.
- Mention %s or locations (NE/NW/SE/SW/north/east/etc.) if present.
- No fluff or generic megillah; use field specifics if provided. Max ~420 chars."""

"""
- Give 1–2 non-obvious recommendations for next year (timing, MOA layering, VT/R1 fungicide windows, split-N, seed treatment, hybrid tolerance).
- Do not include recommendations for the current season as it has already passed. Focus on next season.
- Only make recommendations based on the findings provided for each field, do not invent threats or make any advice not supported by the flight notes.
- If there are conflicting flight notes (i.e. tar spot was or was not identified), err on the side of caution and do not mention the finding.
"""

USER_TEMPLATE = """Field: {field_name} (ID {field_id}) — Client: {client_name}
Flight notes:
{flight_blob}

Task: Summarize the season (early vs late). Keep it tight (≤420 chars)."""

# and provide targeted next-year actions

def build_flight_blob(row: pd.Series) -> str:
    parts: List[str] = []
    for i in range(1, 7):
        txt = row.get(f"Flight {i}")
        if isinstance(txt, str) and txt.strip():
            parts.append(f"- Flight {i}: {txt.strip()}")
    return "\n".join(parts) if parts else "- No flight narratives available."

def pivot_flights(df: pd.DataFrame) -> pd.DataFrame:
    # Resolve mission_rec -> ag_assistant
    df["resolved_text"] = df["mission_rec"].combine_first(df["ag_assistant"])
    df = df[["field_id", "field_name", "client_name", "farm_name", "crop_name", "area", "pass_number", "resolved_text"]].drop_duplicates(
        subset=["field_id", "pass_number"]
    )
    wide = df.pivot_table(
        index=["field_id", "field_name", "client_name", "farm_name", "crop_name", "area"],
        columns=["pass_number"],
        values="resolved_text",
        aggfunc="first"
    )
    wide.columns = [f"Flight {int(c)}" for c in wide.columns]
    wide = wide.reset_index()
    return wide

def summarize_row(client: OpenAI, model: str, row: pd.Series, retries: int = 3, backoff: float = 2.0) -> str:
    flight_blob = build_flight_blob(row)
    user_prompt = USER_TEMPLATE.format(
        field_name=row["field_name"],
        field_id=row["field_id"],
        client_name=row["client_name"],
        flight_blob=flight_blob
    )

    # Use Responses API with a single-string input; retrieve text from output array.
    # See OpenAI Cookbook Responses API example for usage & output access.
    for attempt in range(retries):
        try:
            resp = client.responses.create(
                model=model,
                input=f"{SYSTEM_TONE}\n\n{user_prompt}"
            )
            # Find the first message-type output and return its text
            msg = next(o for o in resp.output if getattr(o, "type", None) == "message")
            return msg.content[0].text.strip()
        except Exception as e:
            if attempt == retries - 1:
                return f"[LLM error] {e}"
            time.sleep(backoff * (attempt + 1))

def main():
    ap = argparse.ArgumentParser(description="Generate season-oriented field summaries via OpenAI.")
    ap.add_argument("--input", required=True, help="Input CSV path")
    ap.add_argument("--output", help="Output CSV path; default [input]-summarized")
    ap.add_argument("--model", default=MODEL_DEFAULT, help="OpenAI model (default from env LLM_MODEL or gpt-4o-mini)")
    ap.add_argument("--delay", type=float, default=0.25, help="Delay between calls in seconds (simple rate control)")
    args = ap.parse_args()

    # Set output file
    input_path = Path(args.input)
    output = args.output or f"{input_path.stem}-summarized{input_path.suffix}"

    # Auth: set OPENAI_API_KEY in your environment.
    client = OpenAI()  # picks up OPENAI_API_KEY
    df = pd.read_csv(f"{args.input}")
    wide = pivot_flights(df)

    summaries = []
    for _, row in wide.iterrows():
        txt = summarize_row(client, args.model, row)
        summaries.append(txt)
        time.sleep(args.delay)

    wide["field_summary"] = summaries
    wide.to_csv(f"{input_path.parent}/{output}", index=False)
    print(f"Saved: {output}")

if __name__ == "__main__":
    main()
