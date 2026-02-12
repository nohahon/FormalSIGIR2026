import csv

INPUT_CSV = "input_clean.csv"
OUTPUT_CSV = "input_InformProof_with_Den.csv"

FIXED_SENTENCE_PREFIX = (
    "Please take into account the following comment, which specifies the relation "
    "between the underlying Lean and informal statement: "
)

def main():
    with open(INPUT_CSV, newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        if not reader.fieldnames:
            raise ValueError("input_clean.csv has no header row.")

        required_cols = {"augmented_proof", "Den"}
        missing = required_cols - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")

        out_fieldnames = list(reader.fieldnames)
        if "Informal_proof_comment" not in out_fieldnames:
            out_fieldnames.append("Informal_proof_comment")

        rows = []
        for row in reader:
            augmented = (row.get("augmented_proof") or "").strip()
            den = (row.get("Den") or "").strip()

            if den == "":
                # If Den is empty, just copy augmented_proof
                row["Informal_proof_comment"] = augmented
            else:
                # Otherwise: augmented_proof + sentence + Den
                if augmented:
                    row["Informal_proof_comment"] = (
                        augmented + "\n\n" + FIXED_SENTENCE_PREFIX + den
                    )
                else:
                    row["Informal_proof_comment"] = FIXED_SENTENCE_PREFIX + den

            rows.append(row)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    main()
