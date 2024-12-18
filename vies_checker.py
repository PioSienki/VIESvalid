import requests
import re
from datetime import datetime
from fpdf import FPDF

class ViesVatChecker:
    def __init__(self):
        self.api_url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
        
    def clean_vat_number(self, vat_number):
        return re.sub(r'[^A-Z0-9]', '', vat_number.upper())
    
    def check_vat(self, country_code, vat_number):
        cleaned_vat = self.clean_vat_number(vat_number)
        
        headers = {
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': '',
        }
        
        soap_request = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                         xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
            <soapenv:Header/>
            <soapenv:Body>
                <urn:checkVat>
                    <urn:countryCode>{country_code}</urn:countryCode>
                    <urn:vatNumber>{cleaned_vat}</urn:vatNumber>
                </urn:checkVat>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        
        try:
            response = requests.post(self.api_url, headers=headers, data=soap_request)
            response.raise_for_status()
            
            if "valid>true</valid" in response.text:
                return True, "Numer VAT jest aktywny"
            elif "valid>false</valid" in response.text:
                return False, "Numer VAT jest nieaktywny"
            else:
                return False, "Nie można zweryfikować numeru VAT"
                
        except requests.RequestException as e:
            return False, f"Błąd połączenia z API: {str(e)}"

    def generate_pdf_report(self, country_code, vat_number, is_valid, message):
        pdf = FPDF()
        pdf.add_page()
        
        # Używamy standardowej czcionki, żeby uniknąć problemów z DejaVu na Vercel
        pdf.set_font('Helvetica', '', 12)
        
        pdf.cell(0, 10, 'Raport sprawdzenia numeru VAT w systemie VIES', 0, 1, 'C')
        pdf.ln(10)
        
        pdf.cell(0, 10, f'Data sprawdzenia: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(0, 10, f'Kraj: {country_code}', 0, 1)
        pdf.cell(0, 10, f'Numer VAT: {vat_number}', 0, 1)
        pdf.cell(0, 10, f'Status: {"Aktywny" if is_valid else "Nieaktywny"}', 0, 1)
        pdf.cell(0, 10, f'Informacja: {message}', 0, 1)
        
        filename = f'vat_check_{country_code}_{vat_number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf.output(filename)
        return filename
