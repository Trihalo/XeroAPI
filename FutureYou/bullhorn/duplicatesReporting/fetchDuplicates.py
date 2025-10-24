#!/usr/bin/env python3
import argparse
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth import authenticate
from duplicatesHelpers import (
    fetch_entity,
    candidate_spec, contact_spec, company_spec,
    build_duplicate_report_generic, build_duplicate_summary_generic,
    autosize_columns,
)

# Map CLI choice -> Bullhorn config + spec
ENTITY_CONFIG = {
    "candidates": {
        "bh_entity": "Candidate",
        "fields":   "id,firstName,lastName,email,mobile",
        "columns":  ["id","firstName","lastName","email","mobile"],
        "spec_fn":  candidate_spec,
        "short":    "Cand",
        "default_outfile": "candidates_dedup.xlsx",
        "all_sheet_prefix": "Candidates",
    },
    "contacts": {
        "bh_entity": "ClientContact",
        "fields":   "id,firstName,lastName,email,phone,mobile",
        "columns":  ["id","firstName","lastName","email","phone","mobile"],
        "spec_fn":  contact_spec,
        "short":    "Cont",
        "default_outfile": "contacts_dedup.xlsx",
        "all_sheet_prefix": "Contacts",
    },
    "companies": {
        "bh_entity": "ClientCorporation",
        "fields":   "id,name",
        "columns":  ["id","name"],
        "spec_fn":  company_spec,
        "spec_kwargs": {"include_phone": False},
        "short":    "Corp",
        "default_outfile": "companies_dedup.xlsx",
        "all_sheet_prefix": "Companies",
    },
}


def run_one(creds, key: str, mode: str, page_size: int):
    cfg = ENTITY_CONFIG[key]

    rows = fetch_entity(
        restUrl=creds["restUrl"],
        BhRestToken=creds["BhRestToken"],
        entity=cfg["bh_entity"],
        fields=cfg["fields"],
        where_or_query="isDeleted:false",
        mode=mode,
        order_field="id",
        page_size=page_size,
    )

    df_all = (pd.DataFrame(rows, columns=cfg["columns"])
                .sort_values("id")
                .drop_duplicates(subset=["id"]))

    spec_kwargs = cfg.get("spec_kwargs", {})
    spec = cfg["spec_fn"](**spec_kwargs) if spec_kwargs else cfg["spec_fn"]()

    dup_df = build_duplicate_report_generic(df_all, spec)
    dup_sum = build_duplicate_summary_generic(dup_df)

    stats_row = {
        "Entity": key.capitalize(),
        "Total": len(df_all),
        "Duplicate groups (Name+Phone)" if key != "companies" else "Duplicate groups (Name)":
            dup_sum.shape[0],
        "Rows flagged": dup_df.shape[0],
    }
    return df_all, dup_df, dup_sum, stats_row


def write_to_excel(path: str, tables: list[tuple[str, pd.DataFrame]]):
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for sheet_name, df in tables:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        # autosize after writing
        for sheet_name, df in tables:
            autosize_columns(writer.sheets[sheet_name], df)

def main():
    ap = argparse.ArgumentParser(description="Bullhorn duplicates fetcher (Candidates/Contacts/Companies).")
    ap.add_argument("--entity", choices=["candidates", "contacts", "companies", "all"], default="candidates",
                    help="Which entity to process.")
    ap.add_argument("--mode", choices=["search", "query"], default="search",
                    help="Use Bullhorn /search (fast, index-based) or /query (complete, stable).")
    ap.add_argument("--page-size", type=int, default=200, help="Page size for API calls.")
    ap.add_argument("--outfile", default=None,
                    help="Output .xlsx path. If --entity all and not provided, defaults to bh_dedup_report.xlsx.")
    args = ap.parse_args()

    creds = authenticate()

    if args.entity == "all":
        out_path = args.outfile or "bh_dedup_report.xlsx"
        tables: list[tuple[str, pd.DataFrame]] = []
        stats_rows = []

        # run all three and place each into its own group of sheets
        for key in ["candidates", "contacts", "companies"]:
            df_all, dup_df, dup_sum, stats_row = run_one(
                creds, key, args.mode, args.page_size
            )
            cfg = ENTITY_CONFIG[key]
            prefix = cfg["all_sheet_prefix"]
            tables.extend([
                (f"All_{prefix}", df_all),
                (f"PotentialDuplicates_{cfg['short']}", dup_df),
                (f"DuplicateSummary_{cfg['short']}", dup_sum),
            ])
            stats_rows.append(stats_row)

        stats_df = pd.DataFrame(stats_rows, columns=["Entity","Total","Duplicate groups (Name+Phone)","Rows flagged"])
        tables.append(("Stats", stats_df))
        write_to_excel(out_path, tables)
        print(f"Exported → {out_path}")
        print(stats_df.to_string(index=False))
        return

    # single-entity run
    key = args.entity
    df_all, dup_df, dup_sum, stats_row = run_one(
        creds, key, args.mode, args.page_size
    )
    cfg = ENTITY_CONFIG[key]
    out_path = args.outfile or cfg["default_outfile"]

    tables = [
        ("All", df_all),
        ("PotentialDuplicates", dup_df),
        ("DuplicateSummary", dup_sum),
        ("Stats", pd.DataFrame([stats_row])),
    ]
    write_to_excel(out_path, tables)
    print(f"Exported → {out_path}")
    print(pd.DataFrame([stats_row]).to_string(index=False))

if __name__ == "__main__":
    main()
