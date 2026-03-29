import requests
import sys
import os
import base64
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import calendar as cal_module
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()

EXCLUDED_EMPLOYEES = {"Alison Kleuver", "Sarah Thompson", "Emily Wilson", "Samaira Bhojani"}

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken
from helpers.dateStringsHelper import parse_xero_date
from helpers.emailAttachment import sendEmail

with open(os.path.join(os.path.dirname(__file__), "LeaveTypes.json"), "r") as f:
    _leave_type_data = json.load(f)
LEAVE_TYPE_MAP = {lt["LeaveTypeID"]: lt["Name"] for lt in _leave_type_data.get("LeaveTypes", [])}


def build_headers(access_token, tenant_id):
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json"
    }

def upload_to_bigquery(df, key):
    if not isinstance(df, pd.DataFrame):
        raise ValueError("Data passed to upload_to_bigquery must be a DataFrame.")

    key_path = os.getenv("MAC_MERCHANDISING_BQACCESS")
    project_id = "macmerchandising"
    dataset_id = "FinanceData"
    table_id = "AnnualLeave" if key == "annual_leave" else "LeaveApplications"

    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(credentials=credentials, project=project_id)
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )

    print(f"📤 Uploading {len(df)} rows to BigQuery table {table_ref}...")
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()

    print("✅ Upload complete.")

    
# 🧾 Function to fetch employees from Xero Payroll API
def fetchEmployeeList(access_token, tenant_id):
    url = "https://api.xero.com/payroll.xro/1.0/Employees"
    headers = build_headers(access_token, tenant_id)
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        employees = response.json().get("Employees", [])
        print(f"✅ {len(employees)} employees found:")
        return employees
    else:
        print(f"❌ Failed to fetch employees: {response.status_code}")
        return []
    
def fetchAllEmployeeAnnualLeave(access_token, tenant_id, employee_list):
    results = []

    for employee in employee_list:
        first_name = employee.get("FirstName", "").strip()
        last_name = employee.get("LastName", "").strip()
        name = f"{first_name} {last_name}"
        print(f"🔍 Fetching employees for: {name}")

        employee_id = employee.get("EmployeeID")
        state = employee.get("EmployeeGroupName", "Unknown")

        # Fetch single employee record (with LeaveBalances)
        url = f"https://api.xero.com/payroll.xro/1.0/Employees/{employee_id}"
        headers = build_headers(access_token, tenant_id)
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to fetch {name}: {response.status_code} - {response.text}")
            continue
        try:
            employee_data = response.json()["Employees"][0]
            leave_balances = employee_data.get("LeaveBalances", [])
            annual_leave_balance = None
            for leave in leave_balances:
                if leave.get("LeaveName") == "Annual Leave":
                    annual_leave_balance = leave.get("NumberOfUnits")
                    break

            if annual_leave_balance is None: print(f"⚠️ Annual Leave not found for {name}")
            results.append({
                "EmployeeID": employee_id,
                "EmployeeName": name,
                "State": state,
                "AnnualLeaveBalance": annual_leave_balance
            })

        except (KeyError, IndexError) as e:
            print(f"❌ Error parsing leave balance for {name}: {e}")

    return pd.DataFrame(results)


def fetchLeaveApplications(access_token, tenant_id, employees):
    url = "https://api.xero.com/payroll.xro/1.0/LeaveApplications"
    headers = build_headers(access_token, tenant_id)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch leave applications: {response.status_code}")
        return pd.DataFrame()

    applications = response.json().get("LeaveApplications", [])

    employee_name_map = {
        emp["EmployeeID"]: f"{emp['FirstName']} {emp['LastName']}"
        for emp in employees
    }

    results = []
    for app in applications:
        employee_id = app.get("EmployeeID")
        employee_name = employee_name_map.get(employee_id, "Unknown")
        title = app.get("Title", "")
        start_date = parse_xero_date(app.get("StartDate"))
        end_date = parse_xero_date(app.get("EndDate"))

        leave_application_id = app.get("LeaveApplicationID")
        leave_type_id = app.get("LeaveTypeID", "")
        resolved_title = title or LEAVE_TYPE_MAP.get(leave_type_id, "")
        for period in app.get("LeavePeriods", []):
            results.append({
                "LeaveApplicationID": leave_application_id,
                "EmployeeName": employee_name,
                "EmployeeID": employee_id,
                "Title": resolved_title,
                "LeavePeriodStatus": period.get("LeavePeriodStatus"),
                "NumberofUnits": period.get("NumberOfUnits"),
                "PayPeriodStart": parse_xero_date(period.get("PayPeriodStartDate")),
                "PayPeriodEnd": parse_xero_date(period.get("PayPeriodEndDate")),
                "StartDate": start_date,
                "EndDate": end_date,
            })

    df = pd.DataFrame(results)

    scheduled = df[df['LeavePeriodStatus'] == 'SCHEDULED'].drop_duplicates(
        subset=['EmployeeName', 'StartDate', 'EndDate']
    )[['LeaveApplicationID', 'EmployeeName', 'Title', 'StartDate', 'EndDate', 'NumberofUnits']].sort_values('StartDate')

    json.dump(scheduled.to_dict(orient="records"), open("leave_applications.json", "w"), indent=2, default=str)
    print(f"✅ Scheduled leave saved to leave_applications.json ({len(scheduled)} records)")

    return df


def build_leave_email(annual_leave_df, leave_applications_df):
    # Embed logo as base64
    logo_path = os.path.join(os.path.dirname(__file__), "forecastingWebsite", "frontend", "public", "fy.png")
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
    logo_tag = f'<img src="data:image/png;base64,{logo_b64}" alt="FutureYou" height="48" width="auto" style="height:48px; width:auto; display:block; border:0;">' if logo_b64 else ""

    BRAND_PRIMARY = "#003464"  # Navy
    BRAND_RED     = "#F25A57"  # Salmon

    # Filter excluded employees
    al_df = annual_leave_df[~annual_leave_df['EmployeeName'].isin(EXCLUDED_EMPLOYEES)].copy()
    apps_df = leave_applications_df[
        ~leave_applications_df['EmployeeName'].isin(EXCLUDED_EMPLOYEES) &
        (leave_applications_df['LeavePeriodStatus'] == 'SCHEDULED')
    ].copy()

    # Compute scheduled hours per employee and merge (keep in hours)
    scheduled = (
        apps_df.groupby('EmployeeID', as_index=False)['NumberofUnits']
        .sum()
        .rename(columns={'NumberofUnits': 'ScheduledHours'})
    )
    df = al_df.merge(scheduled, on='EmployeeID', how='left')
    df['ScheduledHours'] = df['ScheduledHours'].fillna(0)
    df['ALNow'] = df['AnnualLeaveBalance']
    df['ALIncScheduled'] = df['ALNow'] - df['ScheduledHours']
    df = df.sort_values('EmployeeName').reset_index(drop=True)

    # --- Balances table ---
    rows_html = ""
    for i, row in df.iterrows():
        if pd.isna(row['AnnualLeaveBalance']):
            al_now_str, al_inc_str, inc_extra = "N/A", "N/A", ""
        else:
            al_now_str = f"{row['ALNow']:.2f}"
            al_inc_str = f"{row['ALIncScheduled']:.2f}"
            inc_extra = f' color:{BRAND_RED}; font-weight:bold;' if row['ALIncScheduled'] < 0 else ''
        sched_str = f"{row['ScheduledHours']:.2f}"
        row_bg = "#f5f7fa" if i % 2 == 0 else "#ffffff"
        rows_html += f"""
            <tr style="background:{row_bg};">
                <td style="padding:7px 12px; border-bottom:1px solid #e8e8e8;">{row['EmployeeName']}</td>
                <td style="padding:7px 12px; text-align:right; border-bottom:1px solid #e8e8e8;">{al_now_str}</td>
                <td style="padding:7px 12px; text-align:right; border-bottom:1px solid #e8e8e8;">{sched_str}</td>
                <td style="padding:7px 12px; text-align:right; border-bottom:1px solid #e8e8e8;{inc_extra}">{al_inc_str}</td>
            </tr>"""

    balances_table = f"""
    <table style="border-collapse:collapse; font-family:Raleway,Arial,sans-serif; font-size:13px; width:100%; max-width:760px;">
        <thead>
            <tr style="background:{BRAND_PRIMARY}; color:white;">
                <th style="padding:10px 12px; text-align:left;">Employee</th>
                <th style="padding:10px 12px; text-align:right;">AL Bal (hrs)</th>
                <th style="padding:10px 12px; text-align:right;">Scheduled (hrs)</th>
                <th style="padding:10px 12px; text-align:right;">AL Bal inc. Scheduled</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>"""

    # --- Leave summary table (upcoming only) ---
    today = date.today()
    leave_summary = (
        apps_df.groupby(['EmployeeName', 'StartDate', 'EndDate'], as_index=False)
        .agg(TotalHours=('NumberofUnits', 'sum'), Title=('Title', 'first'))
    )
    leave_summary['StartDate'] = pd.to_datetime(leave_summary['StartDate']).dt.date
    leave_summary['EndDate'] = pd.to_datetime(leave_summary['EndDate']).dt.date
    leave_summary = leave_summary[leave_summary['EndDate'] >= today].sort_values('StartDate').reset_index(drop=True)

    leave_rows = ""
    for i, row in leave_summary.iterrows():
        row_bg = "#f5f7fa" if i % 2 == 0 else "#ffffff"
        hours_off = row['TotalHours']
        date_str = row['StartDate'].strftime("%-d %b %Y") if row['StartDate'] != row['EndDate'] else row['StartDate'].strftime("%-d %b %Y")
        if row['StartDate'] != row['EndDate']:
            date_str = f"{row['StartDate'].strftime('%-d %b')} – {row['EndDate'].strftime('%-d %b %Y')}"
        desc = row['Title'] or "—"
        leave_rows += f"""
            <tr style="background:{row_bg};">
                <td style="padding:7px 12px; border-bottom:1px solid #e8e8e8;">{row['EmployeeName']}</td>
                <td style="padding:7px 12px; border-bottom:1px solid #e8e8e8;">{date_str}</td>
                <td style="padding:7px 12px; border-bottom:1px solid #e8e8e8;">{hours_off:.1f}</td>
                <td style="padding:7px 12px; border-bottom:1px solid #e8e8e8; color:#555;">{desc}</td>
            </tr>"""

    leave_table = f"""
    <table style="border-collapse:collapse; font-family:Raleway,Arial,sans-serif; font-size:13px; width:100%; max-width:760px;">
        <thead>
            <tr style="background:{BRAND_PRIMARY}; color:white;">
                <th style="padding:10px 12px; text-align:left;">Employee</th>
                <th style="padding:10px 12px; text-align:left;">Dates</th>
                <th style="padding:10px 12px; text-align:left;">Hours Off</th>
                <th style="padding:10px 12px; text-align:left;">Description</th>
            </tr>
        </thead>
        <tbody>{leave_rows}
        </tbody>
    </table>"""

    # --- Calendar ---
    unique_leaves = leave_summary[['EmployeeName', 'StartDate', 'EndDate']].copy()

    day_map = {}
    for _, row in unique_leaves.iterrows():
        d = row['StartDate']
        while d <= row['EndDate']:
            day_map.setdefault(d, []).append(row['EmployeeName'])
            d += timedelta(days=1)

    if not day_map:
        calendar_html = "<p style='font-family:Raleway,Arial,sans-serif;'>No scheduled leave found.</p>"
    else:
        leave_months = set((d.year, d.month) for d in day_map)
        # Fill every month in the range, even if empty
        min_ym = min(leave_months)
        max_ym = max(leave_months)
        all_months = []
        y, m = min_ym
        while (y, m) <= max_ym:
            all_months.append((y, m))
            m += 1
            if m > 12:
                m = 1
                y += 1

        colors = ['#2980b9','#c0392b','#27ae60','#d35400','#8e44ad',
                  '#16a085','#e74c3c','#f39c12','#0097a7','#6d4c41',
                  '#7b1fa2','#00897b','#546e7a','#e91e63','#1565c0']
        all_employees = sorted(unique_leaves['EmployeeName'].unique())
        emp_colors = {emp: colors[i % len(colors)] for i, emp in enumerate(all_employees)}

        calendar_html = ""
        for year, month in all_months:
            month_name = cal_module.month_name[month]
            calendar_html += f'<h3 class="cal-heading" style="font-family:Raleway,Arial,sans-serif; color:{BRAND_PRIMARY}; margin:28px 0 8px;">{month_name} {year}</h3>'

            if (year, month) not in leave_months:
                calendar_html += f'<p style="font-family:Raleway,Arial,sans-serif; font-size:13px; color:#888; margin:0 0 16px; padding:12px 16px; background:#f5f7fa; border-left:3px solid #ddd;">No scheduled leave this month.</p>'
                continue

            weeks = cal_module.monthcalendar(year, month)
            calendar_html += f'<div class="cal-wrap" style="overflow-x:auto; -webkit-overflow-scrolling:touch;"><table style="border-collapse:collapse; font-family:Raleway,Arial,sans-serif; font-size:12px; width:100%; min-width:420px; table-layout:fixed;"><thead><tr style="background:{BRAND_PRIMARY}; color:white; text-align:center;"><th style="padding:7px;">Mon</th><th style="padding:7px;">Tue</th><th style="padding:7px;">Wed</th><th style="padding:7px;">Thu</th><th style="padding:7px;">Fri</th><th style="padding:7px; background:#1a2f4a;">Sat</th><th style="padding:7px; background:#1a2f4a;">Sun</th></tr></thead><tbody>'
            for week in weeks:
                calendar_html += "<tr>"
                for col_idx, day in enumerate(week):
                    is_weekend = col_idx >= 5
                    cell_bg = "#e8e8e8" if is_weekend else "#ffffff"
                    if day == 0:
                        calendar_html += f'<td style="border:1px solid #ddd; padding:5px; height:70px; vertical-align:top; background:{cell_bg};"></td>'
                    else:
                        d = date(year, month, day)
                        on_leave = day_map.get(d, [])
                        cell = f'<div style="font-weight:bold; font-size:12px; margin-bottom:3px;">{day}</div>'
                        for emp in on_leave:
                            color = emp_colors.get(emp, '#999')
                            first = emp.split()[0]
                            cell += f'<div style="background:{color}; color:white; border-radius:3px; padding:1px 4px; margin:1px 0; font-size:10px; overflow:hidden;">{first}</div>'
                        calendar_html += f'<td style="border:1px solid #ddd; padding:5px; height:70px; vertical-align:top; background:{cell_bg};">{cell}</td>'
                calendar_html += "</tr>"
            calendar_html += "</tbody></table></div>"

        legend = f'<div style="margin-top:16px; font-family:Raleway,Arial,sans-serif; font-size:12px;"><strong>Legend:</strong><br>'
        for emp in all_employees:
            legend += f'<span style="display:inline-block; background:{emp_colors[emp]}; color:white; border-radius:3px; padding:3px 10px; margin:3px; font-size:11px;">{emp}</span>'
        legend += '</div>'
        calendar_html += legend

    return f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Raleway', Arial, sans-serif; color: #333; max-width: 960px; margin: 0 auto; padding: 0; }}
  .scroll-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  @media (max-width: 600px) {{
    .content-pad {{ padding: 16px !important; }}
    .cal-heading {{ font-size: 15px !important; }}
  }}
</style>
</head>
<body>
    <!-- Header: real table layout for Outlook compatibility -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-bottom:3px solid {BRAND_PRIMARY};">
        <tr>
            <td style="padding:16px 28px;" valign="middle">
                <table cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td valign="middle">{logo_tag}</td>
                        <td valign="middle" style="padding-left:16px; color:{BRAND_PRIMARY}; font-size:20px; font-weight:700; font-family:Raleway,Arial,sans-serif;">Annual Leave Report</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    <div class="content-pad" style="padding:24px 28px;">
        <h3 style="color:{BRAND_PRIMARY}; margin-top:0;">Annual Leave Balances</h3>
        <p style="font-size:12px; color:#666; margin:-8px 0 14px;">
            <strong>AL Bal inc. Scheduled</strong> = current accrued balance minus all upcoming approved &amp; scheduled leave hours.
        </p>
        <div class="scroll-wrap">{balances_table}</div>
        <h3 style="color:{BRAND_PRIMARY}; margin-top:36px;">Scheduled Leave</h3>
        <div class="scroll-wrap">{leave_table}</div>
        <h3 style="color:{BRAND_PRIMARY}; margin-top:36px;">Leave Calendar</h3>
        {calendar_html}
    </div>
</body></html>"""


# 🔁 Main routine for specific client(s)
def main():
    clients = ["FUTUREYOU_RECRUITMENT"]
    for c in clients:
        print(f"\n🔍 Fetching employees for: {c}")
        access_token = getXeroAccessToken(c)
        tenant_id = XeroTenants(access_token)
        employeeList = fetchEmployeeList(access_token, tenant_id)

        annual_leave_df = fetchAllEmployeeAnnualLeave(access_token, tenant_id, employeeList)
        leave_applications_df = fetchLeaveApplications(access_token, tenant_id, employeeList)
        
        json.dump(annual_leave_df.to_dict(orient="records"), open("annual_leave.json", "w"), indent=2, default=str)

        html = build_leave_email(annual_leave_df, leave_applications_df)
        with open("leave_report.html", "w") as f:
            f.write(html)
        print("✅ leave_report.html written.")

        sendEmail(
            recipients=["leo@trihalo.com.au"],
            subject="FutureYou — Annual Leave Report",
            body_text="Please find the annual leave report below.",
            provider="GMAIL",
            body_html=html,
        )
        print("✅ Email sent.")
    
    return 0


if __name__ == "__main__":
    main()
