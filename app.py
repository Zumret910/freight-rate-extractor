import os, json, io
import streamlit as st
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Freight Rate Extractor",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 Freight Rate Extractor")
st.caption(
    "Upload a messy carrier Excel quote sheet → get a clean structured table you can download."
)

# ── Sidebar: API key + instructions ──────────────────────────────────────────
with st.sidebar:
    st.header("Setup")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="Paste your key here…",
        help="Your key is only used for this session and is never stored.",
    )
    st.markdown(
        "**Get a free key** (no credit card needed):  \n"
        "1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)  \n"
        "2. Sign in with any Google account  \n"
        "3. Click **Create API key** → copy it  \n"
        "4. Paste it in the box above"
    )
    st.divider()
    st.markdown(
        "**Extracted columns include:**\n"
        "- Validity From / To\n"
        "- Origin City\n"
        "- Destination City\n"
        "- Port of Discharge\n"
        "- Currency (Ocean Freight)\n"
        "- Ocean Freight 20DC / 40DC / 40HC\n"
        "- Currency (Destination Charges)\n"
        "- Handling Import\n"
        "- Destination Delivery Fee\n"
        "- Environmental Fee\n"
        "- DSV Protect\n"
        "- Grade A Handling\n"
        "- Other Fees"
    )


# ── Schema ────────────────────────────────────────────────────────────────────
class RateEntry(BaseModel):
    validity_from: str = Field(description="Start date of validity in YYYY-MM-DD format.")
    validity_to:   str = Field(description="End date of validity in YYYY-MM-DD format.")
    origin_city:   str = Field(description="Origin port or city name (e.g. Shanghai, Xiamen, Ningbo, Port Klang).")
    destination_city: str = Field(
        description="Destination city for final delivery (e.g. Toronto, Vancouver). "
                    "Extract from the document header/title row such as "
                    "'Import Sea Freight Rates to Toronto' or from a Destination column."
    )
    port_of_discharge: str = Field(
        description="Port of Discharge (POD) — the seaport where the container is offloaded. "
                    "Look for it in: (1) the document filename or title row "
                    "(e.g. 'FCL Jun 2026 Toronto' → Toronto, "
                    "'Import Sea Freight Rates to Toronto' → Toronto), "
                    "(2) a 'Port of Discharge' column, or (3) a POD code column. "
                    "Use the port name or code as written. "
                    "If the document title says 'to Toronto', use 'Toronto'."
    )
    currency: str = Field(
        default="USD",
        description="Currency for ocean freight base rates (e.g. USD, CAD). "
                    "Look for a Cur. or Currency column next to the ocean freight rates.",
    )
    destination_currency: str = Field(
        default="USD",
        description="Currency for destination / local charges (Handling, Delivery, "
                    "Environmental, DSV Protect, Grade A, etc.). "
                    "This may differ from the ocean freight currency — for example "
                    "destination charges may be in CAD while ocean freight is in USD. "
                    "Look for a currency indicator next to the destination charge amounts.",
    )
    ocean_freight_20dc: Optional[float] = Field(None, description="Base ocean freight rate for 20DC or 20GP container.")
    ocean_freight_40dc: Optional[float] = Field(None, description="Base ocean freight rate for 40DC or 40GP container, if listed.")
    ocean_freight_40hc: Optional[float] = Field(None, description="Base ocean freight rate for 40HC container.")
    handling_import_amount: Optional[float] = Field(None, description="Handling or Handover Fee (Import) amount.")
    handling_import_unit:   Optional[str]   = Field(None, description="Unit for handling fee: 'per shipment' or 'per container'.")
    destination_delivery_amount: Optional[float] = Field(None, description="Local delivery / cartage fee to the destination city. Typically charged per container.")
    destination_delivery_unit:   Optional[str]   = Field(None, description="Unit for delivery fee: 'per container' or 'per shipment'.")
    destination_delivery_note:   Optional[str]   = Field(None, description="Any special note about the delivery, e.g. 'live unload only', 'drop and pick'.")
    environment_fee_amount: Optional[float] = Field(None, description="Environmental fee or surcharge amount.")
    environment_fee_unit:   Optional[str]   = Field(None, description="Unit: 'per shipment' or 'per container'.")
    dsv_protect_amount: Optional[float] = Field(None, description="DSV Protect or cargo insurance fee amount.")
    dsv_protect_unit:   Optional[str]   = Field(None, description="Unit: 'per shipment' or 'per container'.")
    grade_a_handling_amount: Optional[float] = Field(None, description="Grade A container handling fee amount.")
    grade_a_handling_unit:   Optional[str]   = Field(None, description="Unit: 'per shipment' or 'per container'.")
    other_fees_amount: Optional[float] = Field(None, description="Total of any other local charges not listed above.")
    other_fees_note:   Optional[str]   = Field(None, description="Short description of what the other fees are.")

class RateSheetExtraction(BaseModel):
    rates: List[RateEntry] = Field(description="One entry per origin-destination lane.")


# ── Column rename map ─────────────────────────────────────────────────────────
RENAME = {
    "validity_from":               "Validity From",
    "validity_to":                 "Validity To",
    "origin_city":                 "Origin City",
    "destination_city":            "Destination City",
    "port_of_discharge":           "Port of Discharge",
    "currency":                    "Currency (Ocean Freight)",
    "destination_currency":        "Currency (Destination Charges)",
    "ocean_freight_20dc":          "Ocean Freight 20DC",
    "ocean_freight_40dc":          "Ocean Freight 40DC/40GP",
    "ocean_freight_40hc":          "Ocean Freight 40HC",
    "handling_import_amount":      "Handling Import (Amount)",
    "handling_import_unit":        "Handling Import (Unit)",
    "destination_delivery_amount": "Destination Delivery Fee (Amount)",
    "destination_delivery_unit":   "Destination Delivery Fee (Unit)",
    "destination_delivery_note":   "Delivery Note",
    "environment_fee_amount":      "Environment Fee (Amount)",
    "environment_fee_unit":        "Environment Fee (Unit)",
    "dsv_protect_amount":          "DSV Protect (Amount)",
    "dsv_protect_unit":            "DSV Protect (Unit)",
    "grade_a_handling_amount":     "Grade A Handling (Amount)",
    "grade_a_handling_unit":       "Grade A Handling (Unit)",
    "other_fees_amount":           "Other Fees (Amount)",
    "other_fees_note":             "Other Fees (Note)",
}

SYSTEM_INSTRUCTION = """You are an expert logistics data analyst extracting structured freight rates from messy carrier quotation spreadsheets.

Extraction rules:
1. Create ONE row per origin city.
2. Destination city: look in the document header/title rows (e.g. 'Import Sea Freight Rates to Toronto', 'FCL Jun 2026 Toronto') or in a Destination City column. Apply the same destination city to all rows.
3. Port of Discharge (POD): look in the document title, filename hint, a 'Port of Discharge' column, or a POD code column. The filename hint will be provided. If the title says 'to Toronto' or 'Toronto', the POD is 'Toronto'. If there is a POD column with a code like 'CAYTО', use that. Apply the same POD to all rows unless explicitly different.
4. Ocean freight currency: look for a 'Cur.' or 'Currency' column next to the ocean freight rates for each origin. Record it in the 'currency' field.
5. Destination/local charges currency: look for a currency label (e.g. 'USD', 'CAD') printed next to each destination charge amount. This may be CAD even if ocean freight is USD. Record it in 'destination_currency'. If ALL destination charges show the same currency, use that. If no currency is shown for destination charges, default to 'USD'.
6. Destination/local charges (Handling, Delivery, Environmental, DSV Protect, Grade A handling, other fees) apply to ALL origin cities unless the document explicitly says otherwise. Copy them to every row.
7. For EVERY fee, capture both the AMOUNT and the UNIT ('per shipment', 'per container', 'per B/L', etc.).
8. The 'destination_delivery' fields are for the local delivery/cartage fee to the destination city (e.g. 'Delivery to Toronto'). This is typically charged per container.
9. Convert all dates to YYYY-MM-DD format.
10. If a container size rate is not listed, leave its field null.
11. For container types: treat '20GP' as ocean_freight_20dc, treat '40GP' or '40DC' as ocean_freight_40dc, and '40HC' as ocean_freight_40hc.
"""


def extract_sheet(csv_text: str, filename_hint: str, api_key: str) -> pd.DataFrame:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Filename hint: {filename_hint}\n\nExtract all FCL ocean freight rates from this carrier quotation data:\n\n{csv_text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RateSheetExtraction,
            temperature=0.1,
        ),
    )
    if not response.text:
        return pd.DataFrame()

    rates = json.loads(response.text).get("rates", [])
    if not rates:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    return df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="FCL Rates", index=False)
        ws = writer.sheets["FCL Rates"]
        for col in ws.columns:
            max_len = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 45)
    return buf.getvalue()


# ── Main UI ───────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload your carrier rate Excel file (.xlsx or .xls)",
    type=["xlsx", "xls"],
    help="You can upload one file at a time. Re-upload to process another file.",
)

run = st.button(
    "Extract Rates",
    type="primary",
    disabled=not (api_key and uploaded),
)

if not api_key:
    st.info("Paste your Gemini API key in the sidebar to get started.")
elif not uploaded:
    st.info("Upload an Excel file above, then click **Extract Rates**.")

if run:
    all_dfs = []
    progress = st.progress(0, text="Reading file…")

    try:
        xl = pd.ExcelFile(uploaded)
        sheets = xl.sheet_names
        total = len(sheets)

        for i, sheet in enumerate(sheets):
            progress.progress((i) / total, text=f"Processing sheet: **{sheet}**")

            df_raw = pd.read_excel(uploaded, sheet_name=sheet, header=None)
            if df_raw.shape[0] < 2 or df_raw.shape[1] < 2:
                continue

            df_c = df_raw.dropna(how="all").dropna(how="all", axis=1)
            if df_c.shape[0] < 2:
                continue

            csv_text = df_c.to_csv(index=False, header=False)
            hint = f"{uploaded.name} | Sheet: {sheet}"

            try:
                df_result = extract_sheet(csv_text, hint, api_key)
                if not df_result.empty:
                    df_result.insert(0, "Source Sheet", sheet)
                    df_result.insert(0, "Source File", uploaded.name)
                    all_dfs.append(df_result)
            except Exception as e:
                st.warning(f"Sheet **{sheet}** skipped — {e}")

        progress.progress(1.0, text="Done!")

    except Exception as e:
        st.error(f"Could not read the file: {e}")

    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)

        st.success(f"Extracted **{len(final_df)} row(s)** from {len(all_dfs)} sheet(s).")
        st.dataframe(final_df, use_container_width=True)

        st.download_button(
            label="⬇ Download Excel",
            data=to_excel_bytes(final_df),
            file_name="Extracted_Freight_Rates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif uploaded:
        st.warning(
            "No freight rates were found. "
            "Make sure the file contains rate data and your API key is correct."
        )
