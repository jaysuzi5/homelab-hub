from django.core.management.base import BaseCommand
import openpyxl
from financial.models import ElectricityUsage
from datetime import datetime


class Command(BaseCommand):
    help = 'Import electricity usage data from Excel file'

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
            ws = wb['Electricity Usage']

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
                data = {
                    'kwh_consumed': clean_value(row[1]),  # Column B
                    'kwh_sent': clean_value(row[2]),  # Column C
                    'net_kwh': clean_value(row[3]),  # Column D
                    'total_cost': clean_value(row[4]),  # Column E
                    'cost_per_kwh': clean_value(row[5]),  # Column F
                    'received_per_kwh': clean_value(row[6]),  # Column G
                    'produced_kwh': clean_value(row[7]),  # Column H
                    'kwh_combined': clean_value(row[8]),  # Column I
                    'percent_from_solar': clean_value(row[9]),  # Column J
                    'savings': clean_value(row[10]),  # Column K
                    'credits': clean_value(row[11]),  # Column L
                    'savings_plus_credits': clean_value(row[12]),  # Column M
                    'ev_mileage': clean_value(row[13]),  # Column N
                    'ev_miles_per_kwh': clean_value(row[14]),  # Column O
                    'ev_usage_kwh': clean_value(row[15]),  # Column P
                    'produced_minus_ev': clean_value(row[16]),  # Column Q
                    'net_bill_minus_credits': clean_value(row[17]),  # Column R
                    'comments': row[18] if row[18] else '',  # Column S
                }

                # Create or update the record
                obj, created = ElectricityUsage.objects.update_or_create(
                    date=record_date,
                    defaults=data
                )

                if created:
                    imported_count += 1
                    self.stdout.write(f"Imported: {record_date.strftime('%Y-%m')}")
                else:
                    updated_count += 1
                    self.stdout.write(f"Updated: {record_date.strftime('%Y-%m')}")

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
