import requests
import sys
import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken


def upload_to_bigquery(results_dict):
    """
    Uploads the annual leave results dictionary to BigQuery.
    """
    key_path = os.getenv("MAC_MERCHANDISING_BQACCESS")
    project_id = "macmerchandising"
    dataset_id = "FinanceData"
    table_id = "AnnualLeave"

    # Convert to DataFrame
    df = pd.DataFrame.from_dict(results_dict, orient='index')

    # Authenticate and create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(credentials=credentials, project=project_id)

    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    # Optional: Define schema (optional, BQ can autodetect)
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # or WRITE_APPEND
        autodetect=True
    )

    print(f"📤 Uploading {len(df)} rows to BigQuery table {table_ref}...")

    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()  # Wait for completion

    print("✅ Upload complete.")
    
    
# 🧾 Function to fetch employees from Xero Payroll API
def fetchEmployeeList(access_token, tenant_id):
    url = "https://api.xero.com/payroll.xro/1.0/Employees"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        employees = response.json().get("Employees", [])
        print(f"✅ {len(employees)} employees found:")
        return employees
    else:
        print(f"❌ Failed to fetch employees: {response.status_code}")
        return []
    
def fetchEmployeeAnnualLeave(access_token, tenant_id, employee_id):
    url = f"https://api.xero.com/payroll.xro/1.0/Employees/{employee_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to fetch employee data: {response.status_code} - {response.text}")
        return None
    data = response.json()
    try:
        employee = data["Employees"][0]
        leave_balances = employee.get("LeaveBalances", [])
        for leave in leave_balances:
            if leave.get("LeaveName") == "Annual Leave":
                return leave.get("NumberOfUnits") 
        print("⚠️ Annual Leave not found in leave balances.")
        return None
    except (KeyError, IndexError) as e:
        print(f"❌ Unexpected data format: {e}")
        return None


# 🔁 Main routine for specific client(s)
def main():
    clients = ["MAC_MERCHANDISING"]
    results_dict = {}

    excluded_names = {"Steven Macdonald", "Francesca Marcon"}

    for c in clients:
        print(f"\n🔍 Fetching employees for: {c}")
        access_token = getXeroAccessToken(c)
        tenant_id = XeroTenants(access_token)
        employeeList = fetchEmployeeList(access_token, tenant_id)

        for employee in employeeList:
            first_name = employee.get("FirstName", "").strip()
            last_name = employee.get("LastName", "").strip()
            name = f"{first_name} {last_name}"

            if name in excluded_names:
                print(f"🚫 Skipping excluded employee: {name}")
                continue

            group = employee.get("EmployeeGroupName", "Unknown")
            employee_id = employee["EmployeeID"]

            print(f"🔍 Fetching annual leave for employee: {name}")
            leave_balance = fetchEmployeeAnnualLeave(access_token, tenant_id, employee_id)

            results_dict[employee_id] = {
                "EmployeeID": employee_id,
                "EmployeeName": name,
                "State": group,
                "AnnualLeaveBalance": leave_balance
            }

    upload_to_bigquery(results_dict)

    return results_dict


if __name__ == "__main__":
    main()
