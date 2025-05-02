# --- Area Mapping ---
consultant_area_mapping = {
    "SMC003 Neha Jain": "Accounting & Finance",
    "SMB002 Kate Stephenson": "Accounting & Finance",
    "SMC005 Bianca Hirschowitz": "Accounting & Finance",
    "SCB010 Ashley Duffy": "Business Support",
    "SCE010 Matthew Walker": "SC, Eng & Manufacturing",
    "SEA001 Emily Wilson": "Executive",
    "SEL001 Suzie Large": "Legal",
    "SRM001 Lisa Chesterman": "Sales, Marketing & Digital",
    "SRA002 Dale Hackney": "Sales, Marketing & Digital",
    "SCA001 Corin Roberts": "Technology",
    "SCA002 Tamsin Clark": "Business Support",
    "SEL007 Emma McGuigan": "Legal",
    "SMC008 Julien Dreschel": "Accounting & Finance",
    "SEL009 Tarryn Kaufmann": "Executive",
    "SRM006 Tarryn Kaufmann": "Sales, Marketing & Digital",
    "SEL010 Shazer Barino": "Legal",
    "SMB007 Samaira Bohjani": "Accounting & Finance",
    "PEK002 Tapiwa Utete": "Technology",
    "SMC010 Chloe Crewdson": "Accounting & Finance",
    "SMC004 Melise Hasip": "Accounting & Finance",
    "SMC004 Mel Hasip": "Accounting & Finance",
    "SMA001 Chris Martin": "Accounting & Finance",
    "SCB013 Sharon Callaghan": "Business Support",
    "PEK001 Kevin Howell": "Technology",
    "SEA002 Ben Wainwright": "Executive",
    "SRA003 Natalie Gibbins": "Sales, Marketing & Digital",
}

# Shared base mapping
base_account_code_mapping = {
    "200": "Revenue - Permanent",
    "210": "Revenue - Temporary and contracts",
    "215": "Revenue - Temp to Perm",
    "220": "Revenue - Fixed term contract",
    "225": "Revenue - Retained - Initial",
    "226": "Revenue - Retained - Shortlist",
    "227": "Revenue - Retained - Completion",
    "228": "Revenue - internal",
    "229": "Perm Candidate Reimbursement",
    "230": "Advertising revenue",
    "240": "Revenue - Advisory Consulting HR",
    "241": "Revenue - Advisory HR outsourced services",
    "245": "Revenue - Advisory - EVP",
    "249": "Revenue - Advisory Search",
    "250": "Revenue - Advisory Transition Services",
    "251": "Revenue - Advisory Leadership Program",
    "260": "Revenue - Other Revenue",
}

# Invoice-specific mapping
account_code_mapping = {
    **base_account_code_mapping,
    "611": "Doubtful Debts Provision"
}

# Journal-specific (does not include 611)
journal_account_code_mapping = base_account_code_mapping.copy()
