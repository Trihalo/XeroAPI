import os
import fitz
import re

def extractInvoiceNumberFromPDF(pdf_file):
    try:
        if not os.path.exists(pdf_file):
            print(f"Error: File not found - {pdf_file}")
            return None
        
        doc = fitz.open(pdf_file)  # Open the PDF file
        
        for page in doc:
            text = page.get_text("text")  # Extract text from the page
            
            # Regular expressions to match different invoice number formats
            patterns = [
                r"Tax\s*Invoice\s*.*?\nInvoice\s*#:\s*([A-Za-z0-9-]+)",  # Handles "Tax Invoice" on a different line
                r"Invoice\s*No[:.\s]*([A-Za-z0-9-]+)",  # Standard "Invoice No: XXXXX"
                r"Invoice\s*Number[:.\s]*([A-Za-z0-9-]+)",  # Some invoices use "Invoice Number"
                r"Inv\s*No[:.\s]*([A-Za-z0-9-]+)"  # Shortened "Inv No."
                r"Invoice\s*#:\s*([A-Za-z0-9-]+)",  # Matches "Invoice #: 00070802"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip() 
        
        print(f"Warning: Invoice number not found in {pdf_file}")
        return None  
    
    except Exception as e:
        print(f"Error processing {pdf_file}: {e}")
        return None

# def main():
#     invoices_dir = "invoices"  # Folder where invoice PDFs are stored
    
#     if not os.path.exists(invoices_dir):
#         print(f"Error: Directory '{invoices_dir}' not found.")
#         return
    
#     pdf_files = [os.path.join(invoices_dir, f) for f in os.listdir(invoices_dir) if f.lower().endswith('.pdf')]
    
#     if not pdf_files:
#         print(f"No PDF files found in the '{invoices_dir}' directory.")
#         return
    
#     for pdf in pdf_files:
#         print(f"Processing: {pdf}")
#         invoice_number = extractInvoiceNumberFromPDF(pdf)
        
#         if invoice_number:
#             print(f"Extracted Invoice Number: {invoice_number}")
#         else:
#             print("No invoice number found.")
        
# if __name__ == "__main__":
#     main()
