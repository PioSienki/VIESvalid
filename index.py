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
        pdf.set_font('Arial', '', 12)
        
        pdf.cell(0, 10, 'Raport sprawdzenia numeru VAT w systemie VIES', 0, 1, 'C')
        pdf.ln(10)
        
        pdf.cell(0, 10, f'Data sprawdzenia: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(0, 10, f'Kraj: {country_code}', 0, 1)
        pdf.cell(0, 10, f'Numer VAT: {vat_number}', 0, 1)
        pdf.cell(0, 10, f'Status: {("Aktywny" if is_valid else "Nieaktywny")}', 0, 1)
        pdf.cell(0, 10, 'Informacja: ' + ('Numer VAT jest aktywny' if is_valid else 'Numer VAT jest nieaktywny'), 0, 1)
        
        return pdf.output(dest='S').encode('latin-1')

@app.get("/")
async def get_form():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sprawdzanie numeru VAT - VIES</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8">
            <div class="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
                <h1 class="text-2xl font-bold mb-6 text-center">Sprawdzanie numeru VAT w systemie VIES</h1>
                <form action="/check-vat" method="post" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Kod kraju:</label>
                        <input type="text" name="country_code" 
                               class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                               required maxlength="2" placeholder="np. PL">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Numer VAT:</label>
                        <input type="text" name="vat_number" 
                               class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                               required placeholder="bez kodu kraju">
                    </div>
                    <button type="submit" 
                            class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                        Sprawdz
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
