import json


def count_accpay_invoices(json_file_path):
    """
    Counts the number of invoices with Type = "ACCPAY" in a JSON file.

    :param json_file_path: Path to the JSON file containing invoice data
    :return: Integer count of ACCPAY invoices
    """
    try:
        with open(json_file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        # Ensure invoices is a list
        invoices = data.get("Invoices", [])
        if not isinstance(invoices, list):
            print("Error: JSON file should contain a list of invoices.")
            return 0

        # Count the invoices with Type "ACCPAY"
        accpay_count = sum(
            1 for invoice in invoices if invoice.get("Type") == "ACCPAY")

        return accpay_count
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading file: {e}")
        return 0


def main():
    json_file_path = "./text1.json"  # Change this to your actual file path
    accpay_invoice_count = count_accpay_invoices(json_file_path)
    print(f"Number of ACCPAY invoices: {accpay_invoice_count}")


if __name__ == "__main__":
    main()
