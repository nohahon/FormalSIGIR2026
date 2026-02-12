"""
clean_csv.py

Usage:
  python clean_csv.py stacks_formal_informal_new.csv

Creates:
  input_clean.csv

Behavior:
  Removes any row where formal_proof OR augmented_proof is empty 
  (after stripping whitespace).
"""

import csv
import sys


OUTPUT_FILE = "input_clean.csv"
REQUIRED_COLS = ("formal_proof", "augmented_proof")


def clean_csv(input_path: str, output_path: str) -> None:
    with open(input_path, newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row.")

        missing = [c for c in REQUIRED_COLS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {missing}. Found: {reader.fieldnames}")

        with open(output_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=list(reader.fieldnames))
            writer.writeheader()

            for row in reader:
                formal = (row.get("formal_proof") or "").strip()
                augmented = (row.get("augmented_proof") or "").strip()

                # Skip rows where either column is empty
                if not formal or not augmented:
                    continue

                writer.writerow(row)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python clean_csv.py stacks_formal_informal_new.csv")
        sys.exit(2)

    input_path = sys.argv[1]
    clean_csv(input_path, OUTPUT_FILE)
    print(f"Wrote cleaned CSV to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
