# INF601 - Advanced Programming in Python
# Samuel Hart
# Mini Project 6

"""Compute the family's weekly chapters and shared monthly target."""

from datetime import UTC, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import Reading

FAMILY_MONTHLY_TARGET = 100
WEEKS_SHOWN = 8
READER_COLOURS = (
    "#0d6efd",
    "#d63384",
    "#198754",
    "#fd7e14",
    "#6f42c1",
    "#20c997",
    "#dc3545",
    "#0dcaf0",
)


def _week_start(local_date):
    """Return the Monday of the local week containing a date."""
    return local_date - timedelta(days=local_date.weekday())


def _month_start_utc(today):
    """Return the first moment of the local month in UTC."""
    local_start = datetime.combine(
        today.replace(day=1),
        time.min,
        tzinfo=timezone.get_current_timezone(),
    )
    return local_start.astimezone(UTC)


def _chart_data(readers, weekly, week_starts):
    """Return the SVG geometry for the weekly bars, ticks and labels."""
    chart_width = 720
    chart_height = 300
    left = 44
    right = 16
    top = 16
    bottom = 44
    plot_width = chart_width - left - right
    plot_height = chart_height - top - bottom
    max_value = max(
        (value for reader in readers for value in weekly[reader.pk]),
        default=0,
    )
    y_max = max(1, max_value)
    group_width = plot_width / WEEKS_SHOWN
    bar_slot = group_width * 0.72 / max(1, len(readers))
    bar_width = max(4, bar_slot * 0.8)

    bars = []
    for week_index, start in enumerate(week_starts):
        group_center = left + group_width * week_index + group_width / 2
        group_left = group_center - (bar_slot * len(readers)) / 2
        for reader_index, reader in enumerate(readers):
            value = weekly[reader.pk][week_index]
            height = plot_height * value / y_max
            x = group_left + reader_index * bar_slot + (bar_slot - bar_width) / 2
            y = top + plot_height - height
            bars.append({
                "x": round(x, 1),
                "y": round(y, 1),
                "width": round(bar_width, 1),
                "height": round(height, 1),
                "colour": READER_COLOURS[reader_index % len(READER_COLOURS)],
                "title": (
                    f"{reader.username}, week of {start.strftime('%b %d')}: "
                    f"{value} chapters"
                ),
            })

    y_ticks = []
    for fraction in (0, 0.5, 1):
        y = top + plot_height - plot_height * fraction
        y_ticks.append({"y": round(y, 1), "label": str(round(y_max * fraction))})

    week_labels = []
    for week_index, start in enumerate(week_starts):
        x = left + group_width * week_index + group_width / 2
        week_labels.append({"x": round(x, 1), "label": start.strftime("%b %d")})

    return {
        "chart": {
            "width": chart_width,
            "height": chart_height,
            "left": left,
            "plot_width": plot_width,
        },
        "bars": bars,
        "y_ticks": y_ticks,
        "week_labels": week_labels,
    }


def build_family_progress(readers):
    """Return weekly chapters per reader and the shared monthly total."""
    today = timezone.localdate()
    current_week = _week_start(today)
    week_starts = [
        current_week - timedelta(weeks=offset)
        for offset in range(WEEKS_SHOWN - 1, -1, -1)
    ]
    first_local = datetime.combine(
        week_starts[0],
        time.min,
        tzinfo=timezone.get_current_timezone(),
    )
    first_utc = first_local.astimezone(UTC)

    reading_rows = Reading.objects.filter(
        book__owner__in=readers,
        logged_at__gte=first_utc,
    ).values_list("book__owner_id", "chapters", "logged_at")

    week_index = {start: index for index, start in enumerate(week_starts)}
    weekly = {reader.pk: [0] * WEEKS_SHOWN for reader in readers}
    for owner_id, chapters, logged_at in reading_rows:
        local_date = timezone.localtime(logged_at).date()
        index = week_index.get(_week_start(local_date))
        if index is not None:
            weekly[owner_id][index] += chapters

    month_total = (
        Reading.objects.filter(
            book__owner__in=readers,
            logged_at__gte=_month_start_utc(today),
        ).aggregate(total=Sum("chapters"))["total"]
        or 0
    )
    left = max(0, FAMILY_MONTHLY_TARGET - month_total)
    percent = min(100, round(month_total * 100 / FAMILY_MONTHLY_TARGET))
    month_label = today.strftime("%B %Y")
    if month_total >= FAMILY_MONTHLY_TARGET:
        sentence = (
            f"In {month_label} the family has read {month_total} chapters "
            f"and reached the target of {FAMILY_MONTHLY_TARGET}."
        )
    else:
        sentence = (
            f"In {month_label} the family has read {month_total} chapters. "
            f"{left} more to reach {FAMILY_MONTHLY_TARGET}."
        )

    reader_rows = []
    for index, reader in enumerate(readers):
        values = weekly[reader.pk]
        reader_rows.append({
            "pk": reader.pk,
            "name": reader.username,
            "colour": READER_COLOURS[index % len(READER_COLOURS)],
            "values": values,
            "no_data": not Reading.objects.filter(book__owner=reader).exists(),
        })

    weeks = []
    for index, start in enumerate(week_starts):
        weeks.append({
            "label": start.strftime("%b %d"),
            "values": [weekly[reader.pk][index] for reader in readers],
        })

    chart = _chart_data(readers, weekly, week_starts)
    return {
        "readers": reader_rows,
        "weeks": weeks,
        "chart": chart["chart"],
        "bars": chart["bars"],
        "y_ticks": chart["y_ticks"],
        "week_labels": chart["week_labels"],
        "month_label": month_label,
        "month_total": month_total,
        "target": FAMILY_MONTHLY_TARGET,
        "left": left,
        "percent": percent,
        "sentence": sentence,
        "no_data_names": [
            row["name"] for row in reader_rows if row["no_data"]
        ],
    }
