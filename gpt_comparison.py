import csv
import json
import os
import time
from openai import OpenAI

# For Exp I & II the input file is stacks_formal_informal_new.csv 
# For Exp III the input file is  input_clean.csv
# For Exp IV the input file is input_InformProof_with_Den.csv
INPUT_CSV = "input_clean.csv" 
OUTPUT_CSV = "output3_new.csv"

# Using gpt 5.2: among variants of gpt 5.2., I don't see THINKING available
MODEL = "gpt-5.2"  

SLEEP_BETWEEN_CALLS_SEC = 0.2
MAX_RETRIES = 5
TIMEOUT_SEC = 60  # not used by SDK directly in all modes, but kept for clarity

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")) # OPENAI_API_KEY obtained from OpenAI Platform. exported as variable at .zshrc


## Prompt for Experiments I & II:
## (NOTE: Prompt for Experiment I is the same below except that the two proofs 
## compared are formal_proof and proof (not augmented proof), and Experiment I 
## has uncertain output too)

# SYSTEM_PROMPT = """You will be given two proofs: formal_proof and augmented_proof. 
# formal_proof is a Lean code for proving a statement.
# augmented_proof is an informal mathematical proof for a statement.

# Answer the following questions:
# 1) Do formal_proof and augmented_proof prove the same statement?
# 2) Are the claims made and proved the same?
# 3) Are the proofs of the claims the same?
# 4) Does the formal_proof has a step that is not present 
# in the the augmented_proof or vice versa?
# # About 4: perhaps make it more precise later, e.g., formal_proof has a package 
# # instead of some steps of the augmented_proof, or vice versa...

# Return ONLY valid JSON with the following schema:
# {
# # Below for Experiment I: Remove Uncertain option below
# #  "same_statement": "yes|no|uncertain",
# #  "same_proof_structure": "yes|no|uncertain",
# #  "same_claims": "yes|no|uncertain",
# #  "shorter_due_to_lemmas_or_packages": {
# #    "formal_proof": "yes|no|uncertain",
# #    "augmented_proof": "yes|no|uncertain",
# #    "which_is_shorter": "formal_proof|augmented_proof|neither|uncertain",
#   "same_statement": "yes|no",
#   "same_claims": "yes|no",
#   "same_claim_proof": "yes|no",
#   "Missing step of the other proof": {
#     "formal_proof": "yes|no",
#     "augmented_proof": "yes|no",
#     "notes": "string"
#   },
#   "brief_justification": "string"
# }

# # Below commented out in the new run
# # Be conservative: if the text does not provide enough info, answer "uncertain".
# Keep brief_justification concise (1-3 sentences).

# # Adding below sentence to hopefully activate GPT 5.2 THINKING:
# In the formal proof you will not be provided by the statement of the 
#  lemmas that are being used in the proof.

# """

## Prompt for Experiment III (modified version of formalalign):
SYSTEM_PROMPT = """You will be given two proofs: formal_proof and augmented_proof. 
formal_proof is a Lean code for proving a statement.
augmented_proof is an informal mathematical proof for a statement. 
Your task is to evaluate the alignment between them. Assign a value between 1 and 5 
to each formal_proof, where:  
1 indicates that the formal_proof is not aligned with the augmented_proof at all. 
5 indicates that the formal_proof is perfectly aligned with the augmented_proof.  
Consider the following criteria while assigning the values:  
1. Semantic Consistency: How accurately does the formal_proof capture the meaning 
of the augmented_proof? 
2. Structural Correspondence: How well does the structure of the formal_proof 
reflect the structure implied in the augmented_proof? 
3. Completeness: Does the formal_proof include all relevant information from 
the augmented_proof? 
4. Precision: Is the formal_proof free from extraneous or incorrect information 
that is not present in the augmented_proof?  

Task: 
1. Read the formal_proof and augmented_proof. 
2. Evaluate their alignment using the criteria above. 
3. Assign a value between 1 and 5 to the evaluation result.
4. Prepare a brief justification of the evaluation. The justification must include 
semantic and structural comparison of the two proofs.

Return ONLY valid JSON with the following schema:
{
  "Alignment Score": "1|2|3|4|5",
  "brief_justification": "string"
}

# Adding below sentence to hopefully activate GPT 5.2 THINKING:
In the formal_proof and the augmented_proof you will not be provided by the statement 
of the lemmas that are being used in the proof.

"""

# Prompt for Experiment IV (modified version of Exp III, adding Den comment 
# to informal proof:
# SYSTEM_PROMPT = """You will be given two proofs: formal_proof and augmented_proof. 
# formal_proof is a Lean code for proving a statement.
# augmented_proof is an informal mathematical proof for a statement. 
# Your task is to evaluate the alignment between them. Assign a value between 1 and 5 
# to each formal_proof, where:  
# 1 indicates that the formal_proof is not aligned with the augmented_proof at all. 
# 5 indicates that the formal_proof is perfectly aligned with the augmented_proof.  
# Consider the following criteria while assigning the values:  
# 1. Semantic Consistency: How accurately does the formal_proof capture the meaning 
# of the augmented_proof? 
# 2. Structural Correspondence: How well does the structure of the formal_proof 
# reflect the structure implied in the augmented_proof? 
# 3. Completeness: Does the formal_proof include all relevant information from 
# the augmented_proof? 
# 4. Precision: Is the formal_proof free from extraneous or incorrect information 
# that is not present in the augmented_proof?  

# Task: 
# 1. Read the formal_proof and augmented_proof. 
# 2. Evaluate their alignment using the criteria above. 
# 3. Assign a value between 1 and 5 to the evaluation result.
# 4. Prepare a brief justification of the evaluation. The justification must include 
# semantic and structural comparison of the two proofs.

# Return ONLY valid JSON with the following schema:
# {
#   "Alignment Score": "1|2|3|4|5",
#   "brief_justification": "string"
# }

# # Adding below sentence to hopefully activate GPT 5.2 THINKING:
# In the formal_proof and the augmented_proof you will not be provided by the statement 
# of the lemmas that are being used in the proof.

# """

def call_model(prompt: str, temperature: float = 0.0) -> str:
    """
    Tries Responses API first (best for newer models), falls back to Chat Completions.
    Includes simple exponential backoff retries.
    """
    backoff = 1.0
    last_err = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Preferred: Responses API
            resp = client.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            text = (resp.output_text or "").strip()
            if text:
                return text
            return ""  # should not happen often
        except Exception as e1:
            last_err = e1
            # Fallback: Chat Completions API
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                text = resp.choices[0].message.content.strip()
                return text
            except Exception as e2:
                last_err = e2
                if attempt == MAX_RETRIES:
                    break
                time.sleep(backoff)
                backoff *= 2

    return f'{{"error":"{str(last_err).replace(chr(34), chr(39))}"}}'

def build_prompt(formal_proof: str, augmented_proof: str) -> str: # For EXP I, II, III replace Informal_proof_comment with augmented_proof
    return (
        "Compare the following proofs.\n\n"
        "formal_proof:\n"
        f"{formal_proof}\n\n" # For EXP I, II, III replace Informal_proof_comment with augmented_proof
        "augmented_proof:\n"
        f"{augmented_proof}\n" # For EXP I, II, III replace Informal_proof_comment with augmented_proof
    )

def ensure_json(text: str) -> str:
    """
    Attempts to validate/normalize JSON. If invalid, wraps as an error JSON.
    """
    try:
        obj = json.loads(text)
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        # If the model returned extra text, try to salvage by extracting first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1]
            try:
                obj = json.loads(candidate)
                return json.dumps(obj, ensure_ascii=False)
            except Exception:
                pass
        return json.dumps({"error": "Invalid JSON returned by model", "raw": text}, ensure_ascii=False)

def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f_in, \
         open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)
        if not reader.fieldnames:
            raise ValueError("CSV appears to have no header row.")

        required = {"formal_proof", "augmented_proof"} # For EXP I, II, III replace Informal_proof_comment with augmented_proof
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV must contain columns: {sorted(required)}. Missing: {sorted(missing)}")

        fieldnames = list(reader.fieldnames) + ["comparison_json"]
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for idx, row in enumerate(reader, start=1):
            formal = (row.get("formal_proof") or "").strip()
            augmented = (row.get("augmented_proof") or "").strip() # For EXP I, II, III replace Informal_proof_comment with augmented_proof

            if not formal and not augmented:
                row["comparison_json"] = json.dumps({
                    "same_statement": "uncertain",
                    "same_claims": "uncertain",
                    "same_proof_structure": "uncertain",
                    "shorter_due_to_lemmas_or_packages": {
                        "formal_proof": "uncertain",
                        "augmented_proof": "uncertain", # For EXP I, II, III replace Informal_proof_comment with augmented_proof
                        "which_is_shorter": "uncertain",
                        "notes": "Both proofs are empty."
                    },
                    "brief_justification": "No content provided."
                }, ensure_ascii=False)
                writer.writerow(row)
                continue

            prompt = build_prompt(formal, augmented)
            raw = call_model(prompt, temperature=0.0)
            row["comparison_json"] = ensure_json(raw)

            writer.writerow(row)
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)

if __name__ == "__main__":
    main()
