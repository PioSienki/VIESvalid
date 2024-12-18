from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path
import os
from vies_checker import ViesVatChecker

app = FastAPI()

# Tworzenie katalogu na raporty jeśli nie istnieje
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Serwowanie plików statycznych
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_form():
    return """
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
                        Sprawdź
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/check-vat")
async def check_vat(country_code: str = Form(...), vat_number: str = Form(...)):
    checker = ViesVatChecker()
    
    try:
        is_valid, message = checker.check_vat(country_code, vat_number)
        filename = checker.generate_pdf_report(country_code, vat_number, is_valid, message)
        
        # Przeniesienie pliku do katalogu reports
        new_path = REPORTS_DIR / filename
        Path(filename).rename(new_path)
        
        return FileResponse(
            path=new_path,
            filename=filename,
            media_type="application/pdf"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
