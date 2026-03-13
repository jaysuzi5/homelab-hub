from django.core.management.base import BaseCommand
import openpyxl
from financial.models import NetWorth
from datetime import datetime


class Command(BaseCommand):
    help = 'Import net worth data from Excel file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='/Volumes/nas/Documents/MS Excel/financial.xlsx',
            help='Path to the Excel file'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb['Net Worth']

            self.stdout.write(f"Reading from {file_path}")
            self.stdout.write(f"Sheet dimensions: {ws.dimensions}")

            imported_count = 0
            updated_count = 0
            skipped_count = 0

            # Skip header row and read data
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
                # Column A is the date
                date_value = row[0]

                # Skip empty rows or invalid dates
                if not date_value:
                    continue

                # Handle datetime objects from Excel
                if isinstance(date_value, datetime):
                    record_date = date_value.date()
                else:
                    try:
                        record_date = datetime.strptime(str(date_value), '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        self.stdout.write(self.style.WARNING(f"Skipping row {row_num}: Invalid date {date_value}"))
                        skipped_count += 1
                        continue

                # Helper function to clean numeric values
                def clean_value(val):
                    """Convert Excel values to valid Python types, handling errors and None."""
                    if val is None:
                        return None
                    # Handle Excel error values like #DIV/0!, #N/A, etc.
                    if isinstance(val, str) and val.startswith('#'):
                        return None
                    # Return numeric values as-is
                    if isinstance(val, (int, float)):
                        return val
                    # Try to convert string to float
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return None

                # Extract data from columns
                net_worth_value = clean_value(row[1])  # Column B

                # Skip if no net worth value
                if net_worth_value is None:
                    skipped_count += 1
                    continue

                data = {
                    'net_worth': net_worth_value,
                    'change_from_previous': clean_value(row[2]),  # Column C
                    'percent_change': clean_value(row[4]),  # Column E
                    'comments': row[7] if row[7] else '',  # Column H
                }

                # Create or update the record
                obj, created = NetWorth.objects.update_or_create(
                    date=record_date,
                    defaults=data
                )

                if created:
                    imported_count += 1
                    self.stdout.write(f"Imported: {record_date.strftime('%Y-%m')} - ${net_worth_value:,.2f}")
                else:
                    updated_count += 1
                    self.stdout.write(f"Updated: {record_date.strftime('%Y-%m')} - ${net_worth_value:,.2f}")

            self.stdout.write(self.style.SUCCESS(
                f"\nImport complete!\n"
                f"  Imported: {imported_count}\n"
                f"  Updated: {updated_count}\n"
                f"  Skipped: {skipped_count}"
            ))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise
