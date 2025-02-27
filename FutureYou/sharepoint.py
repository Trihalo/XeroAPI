from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.authentication_context import AuthenticationContext

# SharePoint site and credentials
site_url = "https://futureyou.sharepoint.com/sites/FutureYouFinance"
username = "intern@future-you.com.au"
password = "BlueChair23$"

# Path to the file you want to upload
local_file_path = "/Users/leo/Documents/Trihalo/Xero API/FutureYou/testexcel.xlsx"
sharepoint_folder_url = "/sites/FutureYouFinance/Shared Documents/Jeremy/ATB"

# Authenticate and connect to SharePoint
auth_context = AuthenticationContext(site_url)
if auth_context.acquire_token_for_user(username, password):
    ctx = ClientContext(site_url, auth_context)
    with open(local_file_path, 'rb') as file_content:
        target_folder = ctx.web.get_folder_by_server_relative_url(sharepoint_folder_url)
        target_file_name = local_file_path.split("/")[-1]
        target_folder.upload_file(target_file_name, file_content).execute_query()
        print(f"File '{target_file_name}' uploaded successfully!")
else:
    print("Authentication failed. Please check your credentials.")
