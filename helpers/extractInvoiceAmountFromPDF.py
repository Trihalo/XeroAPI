import fitz
import re
import os

def extractInvoiceAmountAndGSTFromPDF(pdf_file):
    try:
        if not os.path.exists(pdf_file):
            return None, "0.00"

        doc = fitz.open(pdf_file)

        # 1st option - Extracting specific invoice total, disregarding 'Subtotal'
        total_amount_1 = None
        for page in doc:
            text = page.get_text("text")
            total_match = re.search(r"(?<!Subtotal\s)(Invoice Total|Total Amount|Total AUD|Invoice Total:|Balance Due:)\s*\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
            if total_match:
                total_amount_1 = float(total_match.group(2).replace(",", ""))
                break  # Stop at the first match
        
        # 2nd option - Extracting all currency values and taking the max
        amount_list = []
        gst_amount = "0.00"

        for page in doc:
            text = page.get_text("text")
            dollar_amounts = re.findall(r"\$([\d,]+\.\d{2})", text)
            cleaned_amounts = [float(amt.replace(",", "")) for amt in dollar_amounts]  # Convert to float

            amount_list.extend(cleaned_amounts)

            gst_match = re.search(r"\b(GST(?:\s*10%)?)\s*\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
            if gst_match:
                gst_amount = gst_match.group(2).replace(",", "")

        total_amount_2 = max(amount_list) if amount_list else None
        
        invoice_amount = total_amount_1 if total_amount_1 is not None else total_amount_2
        return invoice_amount, gst_amount

    except Exception as e:
        return None, "0.00"
