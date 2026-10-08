import csv
import io
from typing import List, Tuple, Optional
from pydantic import ValidationError

from app.schemas.job import RecipientSchema

NAME_HEADER_ALIASES = {
    "name",
    "recipient_name",
    "full_name",
    "recipient name",
    "full name",
    "student name",
    "participant name",
}

EMAIL_HEADER_ALIASES = {
    "email",
    "recipient_email",
    "email_address",
    "recipient email",
    "email address",
    "mail",
}


class ParsedRecipientResult:

    def __init__(
        self,
        name: str,
        email: str,
        is_valid: bool,
        error_message: Optional[str] = None,
    ):
        self.name = name
        self.email = email
        self.is_valid = is_valid
        self.error_message = error_message


def parse_recipients_from_file(
    content: bytes, filename: str
) -> Tuple[List[ParsedRecipientResult], Optional[str]]:
    """
    Parses a CSV or Excel (.xlsx/.xls) file and returns a tuple of:
    (list of ParsedRecipientResult items, optional fatal file-level error string)
    """
    ext = filename.lower().split(".")[-1]

    if ext in ("csv", "txt"):
        rows = _parse_csv_content(content)
    elif ext in ("xlsx", "xls"):
        rows = _parse_excel_content(content)
    else:
        return [], f"Unsupported file format '{ext}'. Please upload a .csv or .xlsx file."

    if not rows:
        return [], "The uploaded file contains no data or empty rows."

    # Header identification
    header = [str(cell).strip().lower() for cell in rows[0]]
    name_col_idx = -1
    email_col_idx = -1

    for idx, col in enumerate(header):
        if col in NAME_HEADER_ALIASES and name_col_idx == -1:
            name_col_idx = idx
        elif col in EMAIL_HEADER_ALIASES and email_col_idx == -1:
            email_col_idx = idx

    start_row_idx = 1
    # Fallback if no header row found but 2 columns exist
    if name_col_idx == -1 or email_col_idx == -1:
        if len(rows[0]) >= 2:
            name_col_idx = 0
            email_col_idx = 1
            start_row_idx = 0
        else:
            return [], "Could not identify 'Name' and 'Email' columns in the file headers."

    results: List[ParsedRecipientResult] = []

    for row_num, row in enumerate(rows[start_row_idx:], start=start_row_idx + 1):
        if not row or all(str(c).strip() == "" for c in row):
            continue

        name_val = (
            str(row[name_col_idx]).strip()
            if name_col_idx < len(row)
            else ""
        )
        email_val = (
            str(row[email_col_idx]).strip()
            if email_col_idx < len(row)
            else ""
        )

        try:
            recipient = RecipientSchema(name=name_val, email=email_val)
            results.append(
                ParsedRecipientResult(
                    name=recipient.name,
                    email=str(recipient.email),
                    is_valid=True,
                )
            )
        except ValidationError as ve:
            err_msgs = [
                e["msg"]
                .replace("Value error, ", "")
                .replace("value is not a valid email address: ", "Invalid email: ")
                for e in ve.errors()
            ]
            err_msg = "; ".join(err_msgs)
            display_name = name_val if name_val else f"Row {row_num}"
            results.append(
                ParsedRecipientResult(
                    name=display_name,
                    email=email_val,
                    is_valid=False,
                    error_message=f"Row {row_num}: {err_msg}",
                )
            )
        except Exception as exc:
            display_name = name_val if name_val else f"Row {row_num}"
            results.append(
                ParsedRecipientResult(
                    name=display_name,
                    email=email_val,
                    is_valid=False,
                    error_message=f"Row {row_num}: {str(exc)}",
                )
            )


    return results, None


def _parse_csv_content(content: bytes) -> List[List[str]]:
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader if row]


def _parse_excel_content(content: bytes) -> List[List[str]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheet = wb.active
    rows = []
    for row in sheet.iter_rows(values_only=True):
        row_str = [str(cell) if cell is not None else "" for cell in row]
        if any(cell.strip() for cell in row_str):
            rows.append(row_str)
    return rows
