import requests
import sys
import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import json
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken
from helpers.dateStringsHelper import parse_xero_date

with open("LeaveTypes.json", "r") as f:
    leave_type_data = json.load(f)
leave_type_map = {
    lt["LeaveTypeID"]: lt["Name"]
    for lt in leave_type_data.get("LeaveTypes", [])
}


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
    excluded_names = {"Steven Macdonald", "Francesca Marcon"}
    results = []

    for employee in employee_list:
        first_name = employee.get("FirstName", "").strip()
        last_name = employee.get("LastName", "").strip()
        name = f"{first_name} {last_name}"
        print(f"🔍 Fetching employees for: {name}")

        if name in excluded_names:
            print(f"🚫 Skipping excluded employee: {name}")
            continue

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


def fetchLeaveApplications(access_token, tenant_id, employees, leave_type_map):
    url = "https://api.xero.com/payroll.xro/1.0/LeaveApplications"
    headers = build_headers(access_token, tenant_id)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch leave applications: {response.status_code}")
        return pd.DataFrame()

    applications = response.json().get("LeaveApplications", [])
    # Build ID-to-name map using existing employee data
    employee_name_map = {
        emp["EmployeeID"]: f"{emp['FirstName']} {emp['LastName']}"
        for emp in employees
    }

    results = []
    for app in applications:
        employee_id = app.get("EmployeeID")
        employee_name = employee_name_map.get(employee_id, "Unknown")
        title = app.get("Title", "")
        leave_type_id = app.get("LeaveTypeID")
        leave_type_name = leave_type_map.get(leave_type_id, "Unknown Leave Type")
        
        start_date = parse_xero_date(app.get("StartDate"))
        end_date = parse_xero_date(app.get("EndDate"))
        
        for period in app.get("LeavePeriods", []):
            results.append({
                "EmployeeName": employee_name,
                "EmployeeID": employee_id,
                "Title": title,
                "LeavePeriodStatus": period.get("LeavePeriodStatus"),
                "NumberofUnits": period.get("NumberOfUnits"),
                "PayPeriodStart": parse_xero_date(period.get("PayPeriodStartDate")),
                "PayPeriodEnd": parse_xero_date(period.get("PayPeriodEndDate")),
                "LeaveType": leave_type_name,
                "StartDate": start_date,
                "EndDate": end_date,
            })

    return pd.DataFrame(results)


# 🔁 Main routine for specific client(s)
def main():
    clients = ["MAC_MERCHANDISING"]
    for c in clients:
        print(f"\n🔍 Fetching employees for: {c}")
        access_token = getXeroAccessToken(c)
        tenant_id = XeroTenants(access_token)
        employeeList = fetchEmployeeList(access_token, tenant_id)

        annual_leave_df = fetchAllEmployeeAnnualLeave(access_token, tenant_id, employeeList)
        # Get a list of all of the approved leave requests for the client
        leave_applications_df = fetchLeaveApplications(access_token, tenant_id, employeeList, leave_type_map)
        
    upload_to_bigquery(annual_leave_df, "annual_leave")
    upload_to_bigquery(leave_applications_df, "leave_applications")
    
    return 0


if __name__ == "__main__":
    main()
