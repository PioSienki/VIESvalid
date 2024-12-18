# index.py
from fastapi import FastAPI, Form, HTTPException, Response
from fastapi.responses import HTMLResponse
import requests
import re
from datetime import datetime
from fpdf import FPDF
import xml.etree.ElementTree as ET
from xml.dom import minidom

app = FastAPI()

class ViesVatChecker:
    def __init__(self):
        self.api_url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
        
    def clean_vat_number(self, vat_number):
        return re.sub(r'[^A-Z0-9]', '', vat_number.upper())
    
    def prettify_xml(self, xml_string):
        """Format XML string with proper indentation"""
        try:
            parsed = minidom.parseString(xml_string)
            return parsed.toprettyxml(indent="  ")
        except:
            return xml_string
    
    def parse_vies_response(self, xml_text):
        try:
            xml_text = re.sub(' xmlns="[^"]+"', '', xml_text)
            root = ET.fromstring(xml_text)
            
            response = root.find('.//checkVatResponse')
            if response is None:
                return False, "Unable to process VIES response"
            
            valid = response.find('valid')
            name = response.find('name')
            address = response.find('address')
            
            if valid is not None and valid.text.lower() == 'true':
                details = "VAT number is active"
                if name is not None and name.text:
                    details += f"\nName: {name.text}"
                if address is not None and address.text:
                    details += f"\nAddress: {address.text}"
                return True, details
            else:
                return False, "VAT number is not active"
                
        except ET.ParseError:
            return False, "Error processing VIES response"
    
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
            
            # Store both request and response for logging
            self.last_request = self.prettify_xml(soap_request)
            self.last_response = self.prettify_xml(response.text)
            
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
        
        # Response details
        for line in message.split('\n'):
            pdf.cell(0, 10, line, 0, 1)
        
        # API Communication Log
        pdf.ln(10)
        pdf.cell(0, 10, 'API Communication Log', 0, 1, 'L')
        pdf.ln(5)
        
        # Set smaller font for XML
        pdf.set_font('Courier', '', 8)
        
        # SOAP Request
        pdf.cell(0, 10, 'SOAP Request:', 0, 1)
        for line in self.last_request.split('\n'):
            pdf.cell(0, 5, line.rstrip(), 0, 1)
            
        pdf.ln(5)
        
        # SOAP Response
        pdf.cell(0, 10, 'SOAP Response:', 0, 1)
        for line in self.last_response.split('\n'):
            pdf.cell(0, 5, line.rstrip(), 0, 1)
        
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
