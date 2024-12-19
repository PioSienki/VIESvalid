# index.py
from fastapi import FastAPI, Form, HTTPException, Response
from fastapi.responses import HTMLResponse
import requests
import re
from datetime import datetime
from fpdf import FPDF

app = FastAPI()

class ViesVatChecker:
    def __init__(self):
        self.api_url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
        
    def clean_vat_number(self, vat_number):
        return re.sub(r'[^A-Z0-9]', '', vat_number.upper())
    
    def parse_vies_response(self, xml_text):
        try:
            # Check for validity using regex that handles namespaces
            valid_match = re.search(r'<\w*:?valid>(true|false)</\w*:?valid>', xml_text, re.IGNORECASE)
            if not valid_match:
                return False, "Could not determine VAT number status"
                
            is_valid = valid_match.group(1).lower() == 'true'
            
            # Extract other details
            name_match = re.search(r'<\w*:?name>(.*?)</\w*:?name>', xml_text, re.DOTALL)
            address_match = re.search(r'<\w*:?address>(.*?)</\w*:?address>', xml_text, re.DOTALL)
            
            details = []
            details.append("VAT number is active" if is_valid else "VAT number is not active")
            
            if name_match:
                details.append(f"Name: {name_match.group(1).strip()}")
            if address_match:
                details.append(f"Address: {address_match.group(1).strip()}")
                
            return is_valid, "\n".join(details)
            
        except Exception as e:
            return False, f"Error processing response: {str(e)}"
    
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
            self.last_request = soap_request
            self.last_response = response.text
            return self.parse_vies_response(response.text)
                
        except requests.RequestException as e:
            return False, f"API connection error: {str(e)}"

    def generate_pdf_report(self, country_code, vat_number, is_valid, message):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        
        # Header
        pdf.cell(0, 10, 'VAT Number Verification Report - VIES System', 0, 1, 'C')
        pdf.ln(10)
        
        # Main information
        pdf.cell(0, 10, f'Check Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(0, 10, f'Country: {country_code}', 0, 1)
        pdf.cell(0, 10, f'VAT Number: {vat_number}', 0, 1)
        pdf.cell(0, 10, f'Status: {("Active" if is_valid else "Not active")}', 0, 1)
        
        # Company details
        pdf.ln(5)
        for line in message.split('\n'):
            if line.strip():
                pdf.cell(0, 8, line.strip(), 0, 1)
        
        # API Communication Log
        pdf.ln(10)
        pdf.cell(0, 10, 'API Communication Log', 0, 1)
        
        # SOAP Request
        pdf.set_font('Courier', '', 8)
        pdf.cell(0, 8, 'SOAP Request:', 0, 1)
        request_lines = self.last_request.strip().split('\n')
        for line in request_lines:
            if line.strip():
                pdf.cell(0, 4, line.strip(), 0, 1)
        
        # SOAP Response
        pdf.ln(5)
        pdf.cell(0, 8, 'SOAP Response:', 0, 1)
        response_lines = self.last_response.strip().split('\n')
        for line in response_lines:
            if line.strip():
                pdf.cell(0, 4, line.strip(), 0, 1)
        
        return pdf.output(dest='S').encode('latin-1')

@app.get("/")
async def get_form():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VAT Number Verification - VIES</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8">
            <div class="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
                <h1 class="text-2xl font-bold mb-6 text-center">VAT Number Verification - VIES System</h1>
                <form action="/check-vat" method="post" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Country code:</label>
                        <input type="text" name="country_code" 
                               class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                               required maxlength="2" placeholder="e.g. PL">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">VAT number:</label>
                        <input type="text" name="vat_number" 
                               class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                               required placeholder="without country code">
                    </div>
                    <button type="submit" 
                            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Verify
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)

@app.post("/check-vat")
async def check_vat(country_code: str = Form(...), vat_number: str = Form(...)):
    checker = ViesVatChecker()
    
    try:
        is_valid, message = checker.check_vat(country_code, vat_number)
        pdf_content = checker.generate_pdf_report(country_code, vat_number, is_valid, message)
        
        filename = f'vat_check_{country_code}_{vat_number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

