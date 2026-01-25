
import frappe
from frappe.desk.doctype.event.event import Event
from frappe.desk.reportview import get_filters_cond
from frappe.utils.user import get_enabled_system_users
from frappe.desk.doctype.notification_settings.notification_settings import (
	is_email_notifications_enabled_for_type,
)

from frappe.utils import (
	nowdate, get_datetime, formatdate, add_days, 
	add_months, add_years, getdate, date_diff, format_datetime, 
	get_fullname, month_diff, now_datetime
)
from datetime import date, datetime


weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

class Event(Event):
	def autoname(self):
		if not self.event_date:
			frappe.throw("Event Date is required for naming")
		
		date_part = formatdate(self.event_date, "yyMMdd")
		reminder_prefix = self.reminder_type or "EVT"
		prefix = f"{reminder_prefix}{date_part}"
		
		existing = frappe.get_all(
			"Event",
			filters={
				"name": ["like", f"{prefix}%"]
			},
			pluck="name",
			order_by="name desc",
			limit=1
		)
		
		if existing:
			last_number = int(existing[0][-3:])
			new_number = last_number + 1
		else:
			new_number = 1
		
		self.name = f"{prefix}{new_number:03d}"

	def create_repeat_events(self):
		if not self.repeat_this_reminder or not self.repeat_reminder_till:
			return
		
		if getdate(self.repeat_reminder_till) <= getdate(self.event_date):
			frappe.throw("Repeat Reminder Till date must be after Event Date")
		
		max_occurrences = self.get_max_occurrences()
		existing_repeats = self.get_existing_repeat_events()
		
		created_count = 0
		current_date = getdate(self.event_date)
		occurrence_count = 0
		
		while current_date < getdate(self.repeat_reminder_till) and occurrence_count < max_occurrences:
			current_date = self.get_next_occurrence_date(current_date)
			
			if current_date > getdate(self.repeat_reminder_till):
				break
			
			occurrence_count += 1
			
			if current_date in existing_repeats:
				continue
			
			self.create_single_repeat_event(current_date)
			created_count += 1
		
		if created_count > 0:
			frappe.msgprint(f"Created {created_count} repeat events successfully")

	def get_max_occurrences(self):
		limits = {
			"Daily": 365,
			"Weekly": 104,
			"Monthly": 60,
			"Yearly": 10
		}
		return limits.get(self.repeat_reminder_on, 365)

	def get_existing_repeat_events(self):
		existing = frappe.get_all(
			"Event",
			filters={
				"parent_event": self.name,
				"is_repeat_event": 1
			},
			pluck="event_date"
		)
		return set(existing)

	def get_next_occurrence_date(self, current_date):
		if self.repeat_reminder_on == "Daily":
			return add_days(current_date, 1)
		elif self.repeat_reminder_on == "Weekly":
			return add_days(current_date, 7)
		elif self.repeat_reminder_on == "Monthly":
			return add_months(current_date, 1)
		elif self.repeat_reminder_on == "Yearly":
			return add_years(current_date, 1)
		else:
			frappe.throw(f"Invalid repeat frequency: {self.repeat_reminder_on}")

	def create_single_repeat_event(self, new_date):
		repeat_event = frappe.get_doc({
			"doctype": "Event",
			"event_date": new_date,
			"subject": self.subject,
			"description": self.description,
			"reminder_type": self.reminder_type,
			"event_category": self.event_category,
			"event_type": self.event_type,
			"color": self.color,
			"is_repeat_event": 1,
			"parent_event": self.name,
			"repeat_this_reminder": 0, 
		})
		
		if hasattr(self, 'event_participants'):
			for participant in self.event_participants:
				repeat_event.append('event_participants', {
					'reference_doctype': participant.reference_doctype,
					'reference_docname': participant.reference_docname
				})
		
		repeat_event.insert(ignore_permissions=True)
		return repeat_event


def before_save(doc, method=None):
	if doc.event_date:
		from frappe.utils import get_datetime
		event_datetime = get_datetime(doc.event_date)
		doc.starts_on = event_datetime.replace(hour=0, minute=0, second=0)
		doc.ends_on = event_datetime.replace(hour=23, minute=59, second=0)

def on_update(doc,method):
	if doc.repeat_this_reminder and not doc.is_repeat_event:
		doc.create_repeat_events()

def custom_send_email_digest():
	today = getdate()

	events = custom_get_events(today, today)
	if events:
		for e in events:
			e.starts_on = format_datetime(e.starts_on, "hh:mm a")
			if e.all_day:
				e.starts_on = "All Day"

			if e.send_reminder_to_participant == 1:
				event_doc = frappe.get_cached_doc("Event", e.name)
				for row in event_doc.event_participants:
					frappe.sendmail(
						recipients=row.email,
						subject=e.subject,
						message=e.description,
						header=[frappe._("Events in Today's Calendar"), "blue"],
					)


@frappe.whitelist()
def custom_get_events(
	start: date, end: date, user: str | None = None, for_reminder: bool = False, filters=None
) -> list[frappe._dict]:
	user = user or frappe.session.user
	EventLikeDict: TypeAlias = Event | frappe._dict
	resolved_events: list[EventLikeDict] = []

	if isinstance(filters, str):
		filters = json.loads(filters)

	filter_condition = get_filters_cond("Event", filters, [])

	tables = ["`tabEvent`"]
	if "`tabEvent Participants`" in filter_condition:
		tables.append("`tabEvent Participants`")

	event_candidates: list[EventLikeDict] = frappe.db.sql(
		"""
		SELECT `tabEvent`.name,
				`tabEvent`.subject,
				`tabEvent`.description,
				`tabEvent`.color,
				`tabEvent`.starts_on,
				`tabEvent`.ends_on,
				`tabEvent`.owner,
				`tabEvent`.all_day,
				`tabEvent`.event_type,
				`tabEvent`.repeat_this_event,
				`tabEvent`.repeat_on,
				`tabEvent`.repeat_till,
				`tabEvent`.monday,
				`tabEvent`.tuesday,
				`tabEvent`.wednesday,
				`tabEvent`.thursday,
				`tabEvent`.friday,
				`tabEvent`.saturday,
				`tabEvent`.sunday,
				`tabEvent`.send_reminder_to_participant
		FROM {tables}
		WHERE (
				(
					(date(`tabEvent`.starts_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (date(`tabEvent`.ends_on) BETWEEN date(%(start)s) AND date(%(end)s))
					OR (
						date(`tabEvent`.starts_on) <= date(%(start)s)
						AND date(`tabEvent`.ends_on) >= date(%(end)s)
					)
				)
				OR (
					date(`tabEvent`.starts_on) <= date(%(start)s)
					AND `tabEvent`.repeat_this_event=1
					AND coalesce(`tabEvent`.repeat_till, '3000-01-01') > date(%(start)s)
				)
			)
		{reminder_condition}
		{filter_condition}
		AND (
				`tabEvent`.event_type='Public'
				OR `tabEvent`.owner=%(user)s
				OR EXISTS(
					SELECT `tabDocShare`.name
					FROM `tabDocShare`
					WHERE `tabDocShare`.share_doctype='Event'
						AND `tabDocShare`.share_name=`tabEvent`.name
						AND `tabDocShare`.user=%(user)s
				)
			)
		AND `tabEvent`.status='Open'
		ORDER BY `tabEvent`.starts_on""".format(
			tables=", ".join(tables),
			filter_condition=filter_condition,
			reminder_condition="AND `tabEvent`.send_reminder = 1" if for_reminder else "",
		),
		{
			"start": start,
			"end": end,
			"user": user,
		},
		as_dict=True,
	)

	def resolve_event(e: EventLikeDict, target_date: "date", repeat_till: "date"):
		"""Record the event if it falls within the date range and is not excluded by the weekday."""
		if e.repeat_on == "Weekly" and not e[weekdays[target_date.weekday()]]:
			return

		if not (
			e.starts_on.date() <= target_date
			and target_date >= start
			and target_date <= end
			and target_date <= repeat_till
		):
			return

		ends_on_date = add_days(target_date, (e.ends_on - e.starts_on).days) if e.ends_on else None

		if ends_on_date and e.repeat_till and ((ends_on_date > e.repeat_till) or (ends_on_date < start)):
			return

		new_event = e.copy()

		new_event.original_starts_on = new_event.starts_on
		new_event.original_ends_on = new_event.ends_on

		new_event.starts_on = datetime.combine(target_date, e.starts_on.time())
		new_event.ends_on = datetime.combine(ends_on_date, e.ends_on.time()) if ends_on_date else None

		resolved_events.append(new_event)

	for e in event_candidates:
		if not e.repeat_this_event:
			resolved_events.append(e)
			continue

		if e.repeat_till and e.repeat_till < start:
			continue

		repeat_till = getdate(e.repeat_till or "3000-01-01")

		if e.repeat_on == "Daily":
			target_date = start
			while target_date <= end:
				resolve_event(e, target_date=target_date, repeat_till=repeat_till)
				target_date = add_days(target_date, 1)

		elif e.repeat_on == "Weekly":
			target_date = start
			while target_date <= end:
				resolve_event(e, target_date=target_date, repeat_till=repeat_till)
				target_date = add_days(target_date, 1)  # Increment by 1 to capture multiple days in the week

		elif e.repeat_on == "Monthly":
			first_occurence_in_range = e.starts_on.date()
			jump_ahead = month_diff(start, first_occurence_in_range) - 1
			target_date = add_months(first_occurence_in_range, jump_ahead)

			while target_date <= end:
				resolve_event(e, target_date=target_date, repeat_till=repeat_till)
				target_date = add_months(target_date, 1)

		elif e.repeat_on == "Yearly":
			first_occurence_in_range = e.starts_on.date()
			jump_ahead = month_diff(start, first_occurence_in_range) // 12
			target_date = add_years(first_occurence_in_range, jump_ahead)

			while target_date <= end:
				resolve_event(e, target_date=target_date, repeat_till=repeat_till)
				target_date = add_years(target_date, 1)

	# Remove events that are not in the range and boolean weekdays fields
	for event in resolved_events:
		for fieldname in weekdays:
			event.pop(fieldname, None)

	return resolved_events