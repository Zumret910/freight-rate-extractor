# Freight Rate Extractor

Converts messy carrier Excel quote sheets into a clean, structured table — no technical knowledge needed.

## What it extracts

| Column | Example |
|--------|---------|
| Validity From / To | 2026-06-01 / 2026-06-14 |
| Origin City | Shanghai, Xiamen, Ningbo … |
| Destination City | Toronto |
| Currency | USD |
| Ocean Freight 20DC | 6150 |
| Ocean Freight 40HC | 7200 |
| Handling Import (Amount) | 50 |
| Handling Import (Unit) | per shipment |
| **Destination Delivery Fee (Amount)** | **350** |
| **Destination Delivery Fee (Unit)** | **per container** |
| Delivery Note | live unload only |
| Environment Fee (Amount) | 2.50 |
| Environment Fee (Unit) | per shipment |
| DSV Protect (Amount) | 10 |
| DSV Protect (Unit) | per shipment |
| Grade A Handling (Amount) | 85 |
| Grade A Handling (Unit) | per shipment |
| Other Fees | … |
| Source File | DSV_Quote.xlsx |

## How to run (browser only, no install needed)

1. Go to **[colab.google.com](https://colab.google.com)**
2. Click **File → Open notebook → GitHub**
3. Paste your GitHub repository URL and open `FreightRateExtractor.ipynb`
4. In the notebook, find the line that says `PASTE_YOUR_KEY_HERE` and replace it with your Gemini API key
   - Get a **free** key at: https://aistudio.google.com/apikey (sign in with Google, no credit card)
5. Click **Runtime → Run all**
6. When asked, upload your Excel file
7. The clean file downloads automatically

## API Key — is it free?

Yes. The Gemini API free tier gives you **1,500 requests per day** at no cost. Processing one Excel file uses 1 request. No credit card required.

## Supported file formats

- `.xlsx` (Excel)
- `.xls` (older Excel)
- `.csv`
