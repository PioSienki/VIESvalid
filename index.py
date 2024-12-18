# index.py
from fastapi import FastAPI, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
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
    
    def format_xml(self, xml_string):
        """Format XML string for PDF display with strict width control"""
        try:
            # Remove excess whitespace and format basic structure
            xml_string = re.sub(r'\s+', ' ', xml_string)
            xml_string = re.sub(r'> <', '>\n<', xml_string)
            
            lines = xml_string.split('\n')
            formatted_lines = []
            indent = 0
            max_width = 80  # Maximum line width
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Decrease indent for closing tags
                if line.startswith('</'):
                    indent = max(0, indent - 1)
                
                # Add indentation
                indented_line = '  ' * indent + line
                
                # Split long lines
                while len(indented_line) > max_width:
                    split_point = indented_line.rfind(' ', 0, max_width)
                    if split_point == -1:
                        split_point = max_width
                    
                    formatted_lines.append(indented_line[:split_point])
                    indented_line = '  ' * (indent + 1) + indented_line[split_point:].lstrip()
                
                formatted_lines.append(indented_line)
                
                # Increase indent for opening tags
                if not line.startswith('</') and not line.endswith('/>'):
                    indent += 1
                
            return formatted_lines
        except:
            # Fallback to basic formatting if something goes wrong
            return [line.strip() for line in xml_string.split('\n') if line.strip()]

    def parse_vies_response(self, xml_text):
        try:
            valid_match = re.search(r'<\w*:?valid>(true|false)</\w*:?valid>', xml_text, re.IGNORECASE)
            if not valid_match:
                return False, "Could not determine VAT number status"
                
            is_valid = valid_match.group(1).lower() == 'true'
            
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
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_margins(20, 20, 20)
        pdf.set_font('Arial', '', 12)
        
        # Header
        pdf.cell(0, 10, 'VAT Number Verification Report - VIES System', 0, 1, 'C')
        pdf.ln(5)
        
        # Main information
        pdf.cell(0, 10, f'Check Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(0, 10, f'Country: {country_code}', 0, 1)
        pdf.cell(0, 10, f'VAT Number: {vat_number}', 0, 1)
        pdf.cell(0, 10, f'Status: Active', 0, 1)
        
        # Company details
        pdf.ln(5)
        for line in message.split('\n'):
            if line.strip():
                pdf.cell(0, 8, line.strip(), 0, 1)
        
        # API Communication Log
        pdf.ln(5)
        pdf.cell(0, 10, 'API Communication Log', 0, 1)
        
        # Use smaller font for XML
        pdf.set_font('Courier', '', 6)
        line_height = 3
        
        # SOAP Request
        pdf.cell(0, 8, 'SOAP Request:', 0, 1)
        request_lines = self.format_xml(self.last_request)
        for line in request_lines:
            pdf.cell(0, line_height, line, 0, 1)
        
        # SOAP Response
        pdf.ln(3)
        pdf.cell(0, 8, 'SOAP Response:', 0, 1)
        response_lines = self.format_xml(self.last_response)
        for line in response_lines:
            pdf.cell(0, line_height, line, 0, 1)
        
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
                <div id="result" class="mb-4 hidden">
                    <div class="p-4 rounded-md">
                        <p class="text-center text-lg" id="resultMessage"></p>
                    </div>
                </div>
                <form id="vatForm" action="/check-vat" method="post" class="space-y-4">
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
        <script>
            document.getElementById('vatForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                
                try {
                    const response = await fetch('/check-vat', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const contentType = response.headers.get('content-type');
                    const resultDiv = document.getElementById('result');
                    const resultMessage = document.getElementById('resultMessage');
                    resultDiv.className = 'mb-4';
                    
                    if (contentType && contentType.includes('application/pdf')) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        
                        // Get filename from Content-Disposition header
                        const contentDisposition = response.headers.get('Content-Disposition');
                        const filenameMatch = contentDisposition && contentDisposition.match(/filename="(.+)"/);
                        const filename = filenameMatch ? filenameMatch[1] : 'vat_verification.pdf';
                        
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        window.URL.revokeObjectURL(url);
                        
                        resultDiv.className = 'mb-4 bg-green-100';
                        resultMessage.textContent = 'VAT number is active. Downloading verification report...';
                    } else {
                        const data = await response.json();
                        resultDiv.className = 'mb-4 bg-red-100';
                        resultMessage.textContent = data.message;
                    }
                } catch (error) {
                    console.error('Error:', error);
                    const resultDiv = document.getElementById('result');
                    const resultMessage = document.getElementById('resultMessage');
                    resultDiv.className = 'mb-4 bg-red-100';
                    resultMessage.textContent = 'An error occurred while verifying the VAT number.';
                }
            });
        </script>
    </body>
    </html>
    """)

@app.post("/check-vat")
async def check_vat(country_code: str = Form(...), vat_number: str = Form(...)):
    checker = ViesVatChecker()
    
    try:
        is_valid, message = checker.check_vat(country_code, vat_number)
        
        if not is_valid:
            return JSONResponse(content={"message": message})
        
        # Extract company name from message
        company_name = "unknown"
        for line in message.split('\n'):
            if line.startswith('Name:'):
                company_name = line.replace('Name:', '').strip()
                # Clean company name from invalid characters
                company_name = re.sub(r'[^a-zA-Z0-9\s-]', '', company_name)
                company_name = company_name.replace(' ', '-')
                break
        
        pdf_content = checker.generate_pdf_report(country_code, vat_number, is_valid, message)
        
        # New filename format
        safe_company_name = company_name[:30]  # Limit company name length
        filename = f'VIES_{country_code}_{vat_number}_{safe_company_name}.pdf'
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
