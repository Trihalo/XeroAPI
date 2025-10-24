#!/usr/bin/env python3
import re
from typing import Callable, Dict, List, Optional
import pandas as pd
from auth import session, TIMEOUT  # re-use your existing session + TIMEOUT

# ──────────────────────────────────────────────────────────────────────────────
# Normalisers (shared)
# ──────────────────────────────────────────────────────────────────────────────
def norm_series(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.lower()

def normalize_phone_au(raw: Optional[str]) -> str:
    """
    Standardise to AU 10-digit local number (e.g., 0414575868). Else ''.
    Handles +61 / spaces / dashes / parentheses / dropped leading 0.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", str(raw))

    # +61 / 61 → local
    if digits.startswith("61"):
        rest = digits[2:]
        if not rest.startswith("0"):
            rest = "0" + rest
        digits = rest

    # 9-digit mobile w/out 0 → add it
    if len(digits) == 9 and digits.startswith("4"):
        digits = "0" + digits

    # Common landline area codes missing 0
    if len(digits) == 9 and digits[0] in {"2", "3", "7", "8"}:
        digits = "0" + digits

    # Trim extensions if present (keep first 10)
    if len(digits) > 10:
        digits = digits[:10]

    if len(digits) == 10 and digits[0] == "0":
        return digits
    return ""

def normalize_company_name_series(name: pd.Series) -> pd.Series:
    """
    Lowercase, remove punctuation, collapse spaces, and drop trailing legal suffix tokens.
    """
    s = name.fillna("").astype(str).str.lower()
    s = s.str.replace(r"[^a-z0-9 ]+", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    suffixes = {"pty", "ltd", "limited", "pl", "plc"}
    def strip_suffixes(x: str) -> str:
        if not x:
            return x
        toks = x.split()
        while toks and toks[-1] in suffixes:
            toks.pop()
        return " ".join(toks)
    return s.apply(strip_suffixes)

# ──────────────────────────────────────────────────────────────────────────────
# Fetch helper (works for /search or /query with stable paging)
# ──────────────────────────────────────────────────────────────────────────────
def fetch_entity(
    restUrl: str,
    BhRestToken: str,
    entity: str,
    fields: str,
    where_or_query: str = "isDeleted:false",
    page_size: int = 200,
    mode: str = "search",
    order_field: str = "id",
) -> List[Dict]:
    """
    Returns a list of raw JSON dicts as returned by Bullhorn.
    Ensures stable pagination, deduped by 'id'.
    """
    assert mode in {"search", "query"}
    offset = 0
    out, seen = [], set()
    base_url = restUrl + f"{mode}/{entity}"
    key_filter = "query" if mode == "search" else "where"
    sort_key = "sort" if mode == "search" else "orderBy"

    while True:
        resp = session.get(
            base_url,
            params={
                "BhRestToken": BhRestToken,
                key_filter: where_or_query,
                "fields": fields,
                sort_key: order_field,
                "count": page_size,
                "start": offset,
            },
            timeout=TIMEOUT,
        )
        data = resp.json()
        records = data.get("data", []) or []
        if not records:
            break

        for r in records:
            rid = r.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            out.append(r)

        offset += page_size
        print(f"[{entity}] fetched {len(out)} so far...")
        if len(records) < page_size:
            break
    return out

# ──────────────────────────────────────────────────────────────────────────────
# Generic duplicate engine (spec-driven)
# ──────────────────────────────────────────────────────────────────────────────
PartSpec = Dict[str, object]
# PartSpec fields:
#   - cols: List[str]                 # candidate columns; take first non-empty after transform
#   - transform: Callable[[pd.Series], pd.Series]  # vectorised transform
#   - required: bool (default True)   # must be non-empty to be part of the key
#   - out_col: Optional[str]          # write computed series for visibility/debug

def _first_non_empty(df: pd.DataFrame, cols: List[str], transform: Callable[[pd.Series], pd.Series]) -> pd.Series:
    """
    Vectorised: combine multiple columns, taking the first non-empty value after transform.
    """
    vals = pd.Series("", index=df.index, dtype=object)
    for c in cols:
        s = transform(df.get(c, pd.Series(index=df.index, dtype=object)))
        vals = vals.where(vals != "", s)  # fill only where currently empty
    return vals.fillna("").astype(str)

def build_dupkey_columns(df: pd.DataFrame, spec: List[PartSpec], key_col: str = "dupKey") -> pd.DataFrame:
    work = df.copy()
    parts = []
    required_masks = []
    for part in spec:
        cols = part["cols"]
        transform = part["transform"]
        required = part.get("required", True)
        out_col = part.get("out_col")
        series = _first_non_empty(work, cols, transform)
        if out_col:
            work[out_col] = series
        parts.append(series)
        if required:
            required_masks.append(series != "")

    valid_mask = pd.Series(True, index=work.index)
    for m in required_masks:
        valid_mask &= m
    work = work[valid_mask].copy()
    if work.empty:
        work[key_col] = pd.Series(dtype=object)
        return work

    key = parts[0].loc[work.index]
    for p in parts[1:]:
        key = key + "|" + p.loc[work.index]
    work[key_col] = key
    return work

def build_duplicate_report_generic(df: pd.DataFrame, spec: List[PartSpec]) -> pd.DataFrame:
    """
    Returns only rows in groups where dupKey count > 1.
    Adds: dupKey, duplicateCountPerKey, dupIndex.
    """
    if df.empty:
        return pd.DataFrame(columns=["dupKey", "duplicateCountPerKey", "dupIndex", *df.columns.tolist()])

    work = build_dupkey_columns(df, spec, key_col="dupKey")
    if work.empty:
        return pd.DataFrame(columns=["dupKey", "duplicateCountPerKey", "dupIndex", *df.columns.tolist()])

    counts = work.groupby("dupKey").size().rename("duplicateCountPerKey")
    work = work.merge(counts, left_on="dupKey", right_index=True, how="left")
    dup_df = work.loc[work["duplicateCountPerKey"] > 1].copy()
    if dup_df.empty:
        return pd.DataFrame(columns=["dupKey", "duplicateCountPerKey", "dupIndex", *df.columns.tolist()])

    dup_df["dupIndex"] = dup_df.groupby("dupKey").cumcount() + 1
    sort_cols = [c for c in ["duplicateCountPerKey", "lastName", "firstName", "name", "id"] if c in dup_df.columns]
    dup_df = dup_df.sort_values(sort_cols, ascending=[False, True, True, True, True][:len(sort_cols)], kind="mergesort")

    ordered = (
        ["dupKey", "duplicateCountPerKey", "dupIndex"]
        + [c for c in df.columns if c in dup_df.columns]
        + [c for c in dup_df.columns if c not in df.columns and c not in {"dupKey", "duplicateCountPerKey", "dupIndex"}]
    )
    return dup_df[ordered]

def build_duplicate_summary_generic(dup_df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per dupKey with counts + sample IDs + collapsed emails/mobiles if present.
    """
    if dup_df.empty:
        return pd.DataFrame(columns=["dupKey", "recordsPerKey", "sampleIds", "emails", "mobiles", "firstName", "lastName", "name", "phoneKey"])

    def uniq_join(series: pd.Series, limit=5) -> str:
        out, seen = [], set()
        for v in series.fillna("").astype(str):
            v = v.strip()
            if not v or v in seen:
                continue
            seen.add(v); out.append(v)
            if len(out) >= limit:
                break
        return ", ".join(out)

    cols_present = set(dup_df.columns)
    agg = {
        "recordsPerKey": ("id", "size"),
        "sampleIds": ("id", lambda s: ", ".join(map(str, s.head(5)))),
    }
    if "email" in cols_present:
        agg["emails"] = ("email", uniq_join)
    if "mobile" in cols_present:
        agg["mobiles"] = ("mobile", uniq_join)
    if "firstName" in cols_present:
        agg["firstName"] = ("firstName", lambda s: next((x for x in s if str(x).strip()), ""))
    if "lastName" in cols_present:
        agg["lastName"] = ("lastName", lambda s: next((x for x in s if str(x).strip()), ""))
    if "name" in cols_present:
        agg["name"] = ("name", lambda s: next((x for x in s if str(x).strip()), ""))
    if "phoneKey" in cols_present:
        agg["phoneKey"] = ("phoneKey", lambda s: next((x for x in s if str(x).strip()), ""))

    grouped = dup_df.groupby("dupKey", as_index=False).agg(**agg)
    sort_cols = [c for c in ["recordsPerKey", "lastName", "firstName", "name"] if c in grouped.columns]
    grouped = grouped.sort_values(sort_cols, ascending=[False, True, True, True][:len(sort_cols)])

    front = [c for c in ["dupKey", "firstName", "lastName", "name", "phoneKey", "recordsPerKey", "sampleIds", "emails", "mobiles"] if c in grouped.columns]
    rest = [c for c in grouped.columns if c not in front]
    return grouped[front + rest]

def autosize_columns(ws, df: pd.DataFrame) -> None:
    for idx, col in enumerate(df.columns, 0):
        maxlen = max([len(str(col))] + [len(str(x)) for x in df[col].astype(str).values.tolist()])
        ws.set_column(idx, idx, min(maxlen + 2, 60))

# ──────────────────────────────────────────────────────────────────────────────
# Ready-made specs
# ──────────────────────────────────────────────────────────────────────────────
def candidate_spec() -> List[PartSpec]:
    return [
        {"cols": ["firstName"], "transform": norm_series,                                   "required": True,  "out_col": "normFirst"},
        {"cols": ["lastName"],  "transform": norm_series,                                   "required": True,  "out_col": "normLast"},
        {"cols": ["mobile"],    "transform": lambda s: s.apply(normalize_phone_au),         "required": True,  "out_col": "phoneKey"},
    ]

def contact_spec() -> List[PartSpec]:
    # Prefer mobile; fallback to phone
    return [
        {"cols": ["firstName"],          "transform": norm_series,                           "required": True,  "out_col": "normFirst"},
        {"cols": ["lastName"],           "transform": norm_series,                           "required": True,  "out_col": "normLast"},
        {"cols": ["mobile","phone"],     "transform": lambda s: s.apply(normalize_phone_au), "required": True,  "out_col": "phoneKey"},
    ]

def company_spec(include_phone: bool = True) -> List[PartSpec]:
    spec: List[PartSpec] = [
        {"cols": ["name", "companyName"], "transform": normalize_company_name_series,
         "required": True, "out_col": "normCompany"},
    ]
    if include_phone:
        spec.append({
            "cols": ["phone", "phone2", "phone3"],
            "transform": lambda s: s.apply(normalize_phone_au),
            "required": True,
            "out_col": "phoneKey",
        })
    return spec
