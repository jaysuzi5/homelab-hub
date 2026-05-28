"""
Import heating cost history from CornPelletsAndPropane.xls.

Corn/pellet seasons (2007-2008 to 2011-2012):
  - Corn section: used buckets * 25 → lbs, cost_per_bucket / 25 → cost_per_lb
  - Pellets section: used bags, cost_per_bag

Propane seasons (2012-2013 to 2025-2026):
  - gallons, cost per gallon derived from total_cost / gallons
"""
import xlrd
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from financial.models import HeatingRecord

MONTH_MAP = {
    'october': 10, 'november': 11, 'december': 12,
    'january': 1, 'february': 2, 'march': 3,
    'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9,
}

CORN_SEASONS = ['2007-2008', '2008-2009', '2009-2010', '2010-2011', '2011-2012']
PROPANE_SEASONS = [
    '2012-2013', '2013-2014', '2014-2015', '2015-2016', '2016-2017',
    '2017-2018', '2018-2019', '2019-2020', '2020-2021', '2021-2022',
    '2022-2023', '2023-2024', '2024-2025', '2025-2026',
]


def _dec(val):
    if val is None or val == '':
        return None
    try:
        d = Decimal(str(val))
        return d if d != 0 else None
    except InvalidOperation:
        return None


def _parse_corn_pellet_sheet(ws, season):
    """Parse a corn/pellet sheet. Returns list of (fuel_type, month, qty, cost_per_unit)."""
    records = []
    mode = None  # 'corn' or 'pellets'

    for r in range(ws.nrows):
        row = [ws.cell_value(r, c) for c in range(ws.ncols)]
        first = str(row[0]).strip().lower()

        if first.startswith('corn:'):
            mode = 'corn'
            continue
        if first.startswith('pellets:'):
            mode = 'pellets'
            continue
        if first == 'total:' or first.startswith('total:'):
            mode = None
            continue
        if first == 'total' or first == 'month' or first == '':
            continue

        month = MONTH_MAP.get(first)
        if month is None or mode is None:
            continue

        used = _dec(row[3]) if len(row) > 3 else None
        cost_per_unit = _dec(row[5]) if len(row) > 5 else None
        used_cost = _dec(row[7]) if len(row) > 7 else None

        if used_cost is None or used_cost == 0:
            continue  # skip zero months

        if mode == 'corn':
            # Spreadsheet tracks buckets; convert to lbs (1 bucket = 25 lbs)
            if used and cost_per_unit:
                lbs = used * Decimal('25')
                cost_per_lb = cost_per_unit / Decimal('25')
                records.append(('corn', month, lbs, cost_per_lb))
        elif mode == 'pellets':
            if used and cost_per_unit:
                records.append(('pellets', month, used, cost_per_unit))

    return records


def _parse_propane_sheet(ws, season):
    """Parse a propane sheet. Returns list of (fuel_type, month, gallons, cost_per_gal)."""
    records = []
    for r in range(ws.nrows):
        row = [ws.cell_value(r, c) for c in range(ws.ncols)]
        first = str(row[0]).strip().lower()
        month = MONTH_MAP.get(first)
        if month is None:
            continue

        cost = _dec(row[1]) if len(row) > 1 else None
        gallons = _dec(row[3]) if len(row) > 3 else None
        cost_per_gal_raw = _dec(row[5]) if len(row) > 5 else None

        if cost is None or cost == 0:
            continue
        if gallons is None or gallons == 0:
            continue

        cost_per_gal = cost_per_gal_raw or (cost / gallons)
        records.append(('propane', month, gallons, cost_per_gal))

    return records


class Command(BaseCommand):
    help = 'Import heating cost history from CornPelletsAndPropane.xls'

    def add_arguments(self, parser):
        parser.add_argument('--file', default='/Users/jaycurtis/Downloads/CornPelletsAndPropane.xls')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--clear', action='store_true', help='Delete existing records before import')

    def handle(self, *args, **options):
        path = options['file']
        dry_run = options['dry_run']
        clear = options['clear']

        wb = xlrd.open_workbook(path)

        if clear and not dry_run:
            HeatingRecord.objects.all().delete()
            self.stdout.write('Cleared existing records.')

        created = skipped = 0

        for season in CORN_SEASONS:
            if season not in wb.sheet_names():
                self.stdout.write(f'Sheet {season} not found, skipping.')
                continue
            ws = wb.sheet_by_name(season)
            rows = _parse_corn_pellet_sheet(ws, season)
            for fuel_type, month, qty, cpu in rows:
                if dry_run:
                    self.stdout.write(f'  [{season}] {month:02d} {fuel_type}: qty={qty:.2f} cpu={cpu:.6f}')
                    continue
                obj, was_created = HeatingRecord.objects.get_or_create(
                    season=season, month=month, fuel_type=fuel_type,
                    defaults={'quantity': qty, 'cost_per_unit': cpu},
                )
                if was_created:
                    obj.save()  # trigger total_cost calculation
                    created += 1
                else:
                    skipped += 1

        for season in PROPANE_SEASONS:
            if season not in wb.sheet_names():
                self.stdout.write(f'Sheet {season} not found, skipping.')
                continue
            ws = wb.sheet_by_name(season)
            rows = _parse_propane_sheet(ws, season)
            for fuel_type, month, qty, cpu in rows:
                if dry_run:
                    self.stdout.write(f'  [{season}] {month:02d} {fuel_type}: gallons={qty:.1f} cpu={cpu:.6f}')
                    continue
                obj, was_created = HeatingRecord.objects.get_or_create(
                    season=season, month=month, fuel_type=fuel_type,
                    defaults={'quantity': qty, 'cost_per_unit': cpu},
                )
                if was_created:
                    obj.save()
                    created += 1
                else:
                    skipped += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Done. Created: {created}, Skipped (existing): {skipped}'))
        else:
            self.stdout.write('Dry run complete.')
