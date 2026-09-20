# PDF Toolbox

כלי לעריכת PDF בשפה חופשית. עובד גם על קבצים סרוקים (OCR).

## מה הוא יודע
- `הסר ווטרמארק` — מנקה סימני מים (שקופים/צבעוניים) מסריקות, ומוחק שכבות ווטרמארק מקבצי טקסט
- `מחק JET MIDWEST` — מוחק טקסט מהמסמך (גם בסריקה, דרך OCR)
- `מחק עמודים 2-4` / `השאר רק עמודים 1-3` / `סובב את הכל 90` / `הפוך את סדר העמודים`
- אפשר לשרשר: `הסר ווטרמארק, ואז מחק ACME CORP, ואז מחק עמוד 5`

## פריסה ב-Railway
העלה את כל התיקייה ל-GitHub (בלי node_modules). Railway מזהה את ה-`Dockerfile` ובונה לבד.
אין צורך בהגדרות נוספות. אחרי הבנייה: Settings → Networking → Generate Domain.

## הרצה מקומית
```
npm install && npm run build
pip install -r server/requirements.txt   # + tesseract-ocr מותקן במערכת
uvicorn server.main:app --port 3000
```
