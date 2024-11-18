from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import gspread
from pymongo import MongoClient
from gridfs import GridFS
from dotenv import load_dotenv
from bson.objectid import ObjectId
import os
import io
import time
from googleapiclient.errors import HttpError  # Import HttpError

# Load environment variables
load_dotenv(override=True)

# MongoDB Connection
CONNECTION_STRING = os.getenv("MONGO_URI")
client = MongoClient(CONNECTION_STRING)
db = client["Kurukshetra"]
collection = db["Participants"]
fs = GridFS(db)

# Google Sheets Authorization
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "credentials.json"  # Path to your service account file
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gspread_client = gspread.authorize(creds)

# Google Sheets and Drive Setup
sheet_id = "19_fQn1Xf6kODCaHZVcm0-1hWOkSoSamK3zQf8c_pRdc"
sheet = gspread_client.open_by_key(sheet_id).sheet1
sheet_gid = sheet._properties["sheetId"]  # Get the sheet ID for API calls
drive_service = build("drive", "v3", credentials=creds)
sheets_api = build("sheets", "v4", credentials=creds)

# Fetch existing data from the sheet
existing_rows = sheet.get_all_records()
existing_ids = {row["_id"] for row in existing_rows if "_id" in row}

# Upload images to Google Drive and get shareable links
def upload_to_drive(image_binary, file_name):
    try:
        media = MediaIoBaseUpload(io.BytesIO(image_binary), mimetype="image/png")
        file_metadata = {
            "name": file_name,
            "parents": [],  # Add your specific folder ID in Drive if needed
        }
        drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        # Make the file public
        file_id = drive_file.get("id")
        drive_service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"}
        ).execute()
        # Return the shareable link
        return f"https://drive.google.com/uc?id={file_id}"
    except Exception as e:
        print(f"Failed to upload to Google Drive: {e}")
        return None

# Process new rows and insert them into the sheet
new_rows = []
for document in collection.find({}):
    document_id = str(document["_id"])
    
    # Check if the document is already processed
    if document_id not in existing_ids:
        # Basic row data
        new_row = [
            document_id,
            document.get("name", ""),
            document.get("phone", ""),
            document.get("event", ""),
            document.get("role", ""),
            document.get("status", "")
        ]
        
        # Process image if available
        image_id = document.get("image_id")
        if image_id:
            try:
                # Retrieve the image binary data from GridFS
                grid_out = fs.get(image_id)
                image_binary = grid_out.read()
                
                # Generate a file name for the image
                file_name = f"{document.get('name', 'unknown')}_{image_id}.png"
                
                # Upload the image to Google Drive
                image_url = upload_to_drive(image_binary, file_name)
                
                # Add IMAGE formula to the row if upload succeeded
                if image_url:
                    image_b = f'=IMAGE("{image_url}")'
                    new_row.append(image_b)
                else:
                    new_row.append("Image Upload Failed")
            except Exception as e:
                print(f"Failed to process image for {document_id}: {e}")
                new_row.append("Image Not Found")
        else:
            new_row.append("No Image")

        # Append the new row to the list for insertion
        new_rows.append(new_row)

# Insert new rows into Google Sheets if there are any
if new_rows:
    try:
        for row in new_rows:
            sheet.append_row(row, value_input_option="RAW")  # Insert each row
        print(f"Added {len(new_rows)} new rows with images to the sheet.")
    except Exception as e:
        print(f"Failed to add rows to the sheet: {e}")
else:
    print("No new rows to add.")

print("making updates now")
# Clean column values and adjust row heights
column_index = 7  # The column where data needs to be cleaned
# Fetch column values as raw values to avoid formula artifacts
column_values = sheet.col_values(column_index)

# Process column values to clean leading apostrophes
column_values = sheet.col_values(column_index)

# Process and clean values to remove leading apostrophes
cleaned_values = [value.lstrip("'") if value.startswith("'") else value for value in column_values]

# Update the column with cleaned values
for row_index, cleaned_value in enumerate(cleaned_values, start=1):
    sheet.update_cell(row_index, column_index, cleaned_value)

