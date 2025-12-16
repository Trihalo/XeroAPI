import pdfplumber
import os

pdf_path = '/Users/leo/Github/XeroAPI/H2coco/mondiale/TAX INVOICE 02733707 H2COCOSYD (25-Nov-25).PDF'

def analyze_pdf(path):
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"--- Page {i+1} ---")
            text = page.extract_text()
            print("TEXT EXTRACT:")
            print(text)
            print("-" * 20)
            print("TABLES EXTRACT:")
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    print(row)
                print("." * 10)
            print("=" * 40)

if __name__ == "__main__":
    if os.path.exists(pdf_path):
        analyze_pdf(pdf_path)
    else:
        print(f"File not found: {pdf_path}")
